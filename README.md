# Payday Core

Vyper contracts for onchain commitment savings. A factory ERC-721 mints an access NFT and deploys a goal clone. The NFT owner may deposit, complete, or early-exit.

Free unlock when `principal >= target`. Under target, early exit is all-or-nothing: a linear time-decaying fee goes to treasury, the rest to the NFT owner. Optional ERC-4626 idle yield also goes to treasury.

**Stack:** Vyper 0.4.3, [Moccasin](https://cyfrin.github.io/moccasin/), [snekmate](https://github.com/pcaversaccio/snekmate) (`ownable` + `erc721`).

## Layout

```
src/
  payday_factory.vy              # ERC-721 access pass + factory + URI packs
  payday_goal.vy                 # EIP-5202 blueprint implementation
  interfaces/IPaydayFactory.vyi  # Factory surface used by goals
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
| `skim_yield` | anyone | Surplus above nominal principal to treasury |
| `disable_transfers` | NFT owner | Irreversible soulbind for that `token_id` |

Soulbind does not change `tokenURI`. Deposit, complete, and early-exit still work for the fixed owner. There is no admin unlock.

v1 `create_goal` defaults `vault` to `empty(address)`. When a vault is passed, deposits park there; NAV below principal blocks further deposits and skim.

### Parameters

Values in `payday_factory.vy` / `tests/utils/constants.py`:

| Param | Value |
|-------|--------|
| NFT name / symbol | `Payday Goal` / `PAYD` (snekmate symbol max 5 chars) |
| `START_PENALTY_BPS` | 8000 (80%), set by the factory on every goal |
| Min duration | 30 days |
| Max duration | 730 days |
| Min target / min deposit | per-asset, via `set_asset_allowed` |
| ERC-20 / ERC-4626 | Vyper built-ins `IERC20` / `IERC4626` |

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

Not a dynamic NFT. The factory stores three pack URIs (max 432 chars) and writes the full string as `tokenURI` (snekmate base URI is empty):

| State | When | Placeholder pin |
|-------|------|-----------------|
| Created | mint, `principal == 0` | `ipfs://payday/v1/created.json` |
| InProgress | first successful `deposit` | `ipfs://payday/v1/in-progress.json` |
| Completed | `complete()` or `early_exit()` | `ipfs://payday/v1/completed.json` |

Pin real CIDs, then pass them into the factory constructor or call `set_uris` (owner). Linked goals call `set_goal_uri_in_progress` / `set_goal_uri_completed`; those setters reject any other caller.

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

Factory create / soulbind live under `tests/unitary/payday_factory`. Goal deposit / complete / early-exit / yield under `tests/unitary/payday_goal`. NFT transfer and full lifecycle under `tests/integration`. Penalty formula under `tests/fuzz`.

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
    # vault=empty by default
    # penalty is always factory.START_PENALTY_BPS (8000)
)
```

## License

`payday_factory.vy` composes snekmate and is **AGPL-3.0-only**. `payday_goal.vy` is also **AGPL-3.0-only** (see the file header).
