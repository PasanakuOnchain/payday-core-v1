# Payday Core

Vyper contracts for onchain commitment savings. A factory ERC-721 mints an access NFT and deploys a goal clone. The NFT owner may deposit, complete, or early-exit.

Free unlock when `principal >= target`. Under target, early exit is all-or-nothing: a linear time-decaying fee goes to treasury, the rest to the NFT owner.

**Stack:** Vyper 0.4.3, [Moccasin](https://cyfrin.github.io/moccasin/), [snekmate](https://github.com/pcaversaccio/snekmate) (`ownable_2step` + `erc721`).

## Layout

```
src/
  payday_factory.vy              # ERC-721 access pass + factory + URI packs
  payday_goal.vy                 # EIP-5202 blueprint implementation
  interfaces/IPaydayFactory.vyi  # Factory external surface
script/deploy.py                 # Blueprint then factory
tests/                           # Unitary, integration, fuzz
deployments/                     # Chain address placeholders
```

Goals are never constructed with `CREATE` from tests or scripts except as an EIP-5202 blueprint. Every user goal is `create_from_blueprint` (Vyper default `code_offset=3`).

## Protocol

One goal = one NFT = one allowlisted ERC-20. Transfer of the NFT transfers control of the goal. Auth is `ownerOf(token_id)`, not a frozen creator address.

| Action | Who | Rule |
|--------|-----|------|
| `create_goal` | anyone | Asset allowlisted; duration caps; penalty is factory-fixed |
| `deposit` | NFT owner | Anytime, `amount >= min_deposit` |
| `complete` | NFT owner | `principal >= target`; 100% of principal to owner |
| `early_exit` | NFT owner | `principal < target`; fee to treasury, net to owner; closes |
| `disable_transfers` | NFT owner | Irreversible soulbind for that `token_id` |

Soulbind does not change `tokenURI`. Deposit, complete, and early-exit still work for the fixed owner. There is no admin unlock.

### Parameters

Values in `payday_factory.vy` / `tests/utils/constants.py`:

| Param | Value |
|-------|--------|
| NFT name / symbol | `Payday Goal` / `PAYD` (snekmate symbol max 5 chars) |
| `START_PENALTY_BPS` | 8000 (80%), set by the factory on every goal |
| Min duration | 30 days |
| Max duration | 730 days |
| Min target / min deposit | per-asset, via `set_asset_allowed` |
| ERC-20 | Vyper built-in `IERC20` |

Treasury is set at factory deploy. Existing clones keep the treasury snapshotted at `create_goal`. Owner may `set_treasury` for later clones.

### Penalty

The factory writes `START_PENALTY_BPS` (8000) onto every goal. Callers do not choose it. The clone stores that value at creation.

```
# now in [start_time, end_time):
penalty_bps = START_PENALTY_BPS * (end_time - now) // (end_time - start_time)
# now <= start_time: START_PENALTY_BPS
# now >= end_time: 0
```

`fee = principal * penalty_bps / 10_000` (mul before div, rounds down). Quote with `preview_early_exit()`.

### NFT metadata

Not a dynamic NFT. The factory freezes three pack URIs at construction (`URI_CREATED`, `URI_IN_PROGRESS`, `URI_COMPLETED`, max 432 characters). `tokenURI` reads the linked goal and returns one pack:

| State | When | Placeholder pin |
|-------|------|-----------------|
| Created | `principal == 0` and not closed | `ipfs://payday/v1/created.json` |
| InProgress | `principal > 0` and not closed | `ipfs://payday/v1/in-progress.json` |
| Completed | `closed` after `complete()` or `early_exit()` | `ipfs://payday/v1/completed.json` |

Pin real CIDs and pass them into the factory constructor. There is no URI setter. Admin ownership is snekmate `ownable_2step`: `transfer_ownership` sets `pending_owner`, and that account must call `accept_ownership`.

## Setup

Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or any installer that reads `pyproject.toml`):

```bash
uv sync
```

Copy `.env` as needed for live networks. `moccasin.toml` defines `pyevm`, `anvil`, and `sepolia`.

## Tests

```bash
mox test
mox test tests/unitary/payday_factory/test_create_goal.py -v
```

Factory create / soulbind live under `tests/unitary/payday_factory`. Goal deposit / complete / early-exit under `tests/unitary/payday_goal`. NFT transfer and full lifecycle under `tests/integration`. Penalty formula under `tests/fuzz`.

Format Vyper with `mamushi`; Python with `ruff`.

## Deploy

```bash
mox run deploy
```

`script/deploy.py`:

1. `payday_goal.deploy_as_blueprint()` (EIP-5202 preamble `0xfe7100`)
2. `payday_factory.deploy(blueprint, treasury, uri_created, uri_in_progress, uri_completed)`
3. Owner calls `set_asset_allowed(asset, True, min_target, min_deposit)` per stable

Local / titanoboa uses the deployer EOA as treasury. For a named network:

```bash
mox run deploy --network anvil
mox run deploy --network sepolia
```

Write live addresses into `deployments/<chain>.json` after a broadcast. Placeholders in this repo are not deployed contracts.

### Create a goal

```python
goal, token_id = factory.create_goal(
    asset,
    target,
    end_time,  # unix; duration in [30d, 730d]
    # penalty is always factory.START_PENALTY_BPS (8000)
)
```

## License

`payday_factory.vy` composes snekmate and is **AGPL-3.0-only**. `payday_goal.vy` is also **AGPL-3.0-only** (see the file header).

## Monad deployment and verification

`moccasin.toml` includes `monad` (143) and `monad-testnet` (10143), using
[Monad's network settings](https://docs.monad.xyz/developer-essentials/network-information).
Use a Moccasin keystore account for deployment:

```bash
uv run mox run deploy --network monad-testnet --account your-account
```

Record the blueprint, factory, treasury and asset addresses in
`deployments/monad-testnet.json` (or `monad.json`), then run the web ABI sync.
No Monad deployment is recorded yet. Deploy does not automatically verify.

Verification is a separate, read-only script. Fill the hardcoded
`FACTORY_ADDRESS`, `GOAL_BLUEPRINT_ADDRESS`, `ORIGINAL_TREASURY_ADDRESS` and
original metadata URIs in `script/verify.py`. Do not substitute the current
factory treasury if it has changed since deployment. The script verifies the
factory and checks the blueprint bytecode. Addresses are never read from
environment variables or CLI arguments.

Set `ETHERSCAN_API_KEY` in your ignored `.env` for the Monadscan Etherscan V2
explorer, then run:

```bash
uv run mox run verify --network monad-testnet
# Mainnet:
uv run mox run verify --network monad
```

Goal clones are verified separately. `script/verify_goals.py` reads the same
`FACTORY_ADDRESS`, walks every minted access NFT, rebuilds each goal's
constructor arguments from its immutables, and submits the ones the explorer
does not already have source for. Re-run it after new goals are created:

```bash
uv run mox run verify_goals --network monad-testnet
# Mainnet:
uv run mox run verify_goals --network monad
```

Both scripts use the Titanoboa backend described in
[Moccasin's verification guide](https://cyfrin.github.io/moccasin/how-tos/verify_contracts.html),
with an explicit Etherscan chain ID (the installed Moccasin wrapper otherwise
defaults to Ethereum). Factory verification waits for the explorer and fails
on missing addresses, a wrong network, or a mismatched blueprint build.
Goal verification skips contracts that are already verified, keeps going if
one submission fails, and exits with an error if any goal failed.
Neither script deploys or signs a transaction.

The EIP-5202 blueprint is checked against the exact local compiled bytecode.
The installed verification backend does not support publishing blueprint
verification; this local match is **not** explorer source verification.
Use the same Vyper version, dependencies and compiler settings as deployment.
