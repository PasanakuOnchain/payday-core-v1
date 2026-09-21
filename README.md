# Payday Core

Onchain commitment-savings vaults. A factory **ERC-721** (snekmate) mints an access NFT and deploys a **goal** via `create_from_blueprint`. The NFT owner alone may deposit, complete, or early-exit.

Free withdraw if principal ≥ target. Otherwise all-or-nothing early exit with a linear time-decaying penalty to treasury. Optional ERC-4626 idle yield also goes to treasury.

## Architecture

| Contract | Role |
|----------|------|
| `src/payday_factory.vy` | ERC-721 access pass, asset allowlist, URI packs, soulbind |
| `src/payday_goal.vy` | Blueprint implementation: custody, penalty, complete / early-exit |

Goals are **never** constructed with `CREATE` from tests or scripts except as an EIP-5202 blueprint. Every user goal is `create_from_blueprint`.

Transfer of the NFT transfers control of the goal. The owner may call `disable_transfers(token_id)` to soulbind that token **irreversibly**.

## Parameters

| Param | Value |
|-------|--------|
| NFT name / symbol | `Payday Goal` / `PAYD` (snekmate symbol max 5 chars) |
| Suggested `start_penalty_bps` | 2000 (20%) |
| `MAX_START_PENALTY_BPS` | 5000 |
| Min duration | 30 days |
| Max duration | 730 days |
| Min target / min deposit | per-asset, set via `set_asset_allowed` |
| Vault (v1) | `empty(address)` unless `create_goal(..., vault=)` is passed |
| ERC-20 / ERC-4626 | Vyper built-ins `IERC20` / `IERC4626` (no vendored copies) |

### Penalty

```
# now in [start_time, end_time):
penalty_bps = start_penalty_bps * (end_time - now) // (end_time - start_time)
# now <= start_time: start_penalty_bps
# now >= end_time: 0
```

`fee = principal * penalty_bps / 10_000` (mul before div, rounds down).

## NFT metadata (static IPFS)

Not a dynamic NFT. The factory stores three pack URIs and writes `tokenURI[token_id]` on lifecycle transitions:

| State | When | Default pin (replace before prod) |
|-------|------|-------------------------------------|
| Created | mint, `principal == 0` | `ipfs://payday/v1/created.json` |
| InProgress | first successful `deposit` | `ipfs://payday/v1/in-progress.json` |
| Completed | `complete()` or `early_exit()` | `ipfs://payday/v1/completed.json` |

Soulbind does **not** change `tokenURI`. Pin real CIDs, then `set_uris` (owner) or pass them into the factory constructor.

## Blueprint deploy

```bash
# local / titanoboa
mox run deploy
```

`script/deploy.py`:

1. `payday_goal.deploy_as_blueprint()` (EIP-5202 preamble `0xfe7100`; Vyper `create_from_blueprint` default `code_offset=3`)
2. `payday_factory.deploy(blueprint, treasury, uri_created, uri_in_progress, uri_completed)`
3. Owner calls `set_asset_allowed(asset, True, min_target, min_deposit)` per stable

Chain-specific addresses belong in `deployments/<chain>.json` after a live deploy. This repo does not run `npx convex deploy`; use `mox run deploy --network sepolia` when you are ready to broadcast (production deploys only on purpose).

## Tests

```bash
mox test
mox test tests/unitary/payday_factory/test_create_goal.py -v
```

Required cases T1–T16 live under `tests/unitary`, `tests/integration`, and `tests/fuzz`.

## License

`payday_factory.vy` composes snekmate (`ownable` + `erc721`) and is **AGPL-3.0-only**, matching snekmate. `payday_goal.vy` is MIT.
