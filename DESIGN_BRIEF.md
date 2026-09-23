# Payday Core — Design Brief (smart contracts)

**Repo:** `payday-core`  
**Stack:** **Vyper + Moccasin** (not Foundry, not Solidity)  
**Status:** locked for coding-agent handoff (v1)  
**Product spine:** umbrella `../DESIGN_BRIEF.md` / web `../web/DESIGN_BRIEF.md`

---

## One-liner

Factory is an **ERC-721** (snekmate) that **mints an access NFT** and deploys a **goal** via `create_from_blueprint`. NFT owner alone may deposit / complete / early-exit. Free withdraw iff principal ≥ target; else all-or-nothing early exit with linear time-decaying penalty → treasury. Optional ERC-4626 idle yield → treasury.

---



## Goals

1. Deploy **chain-agnostic** (addresses + chain id via Moccasin/deploy config).
2. **Allowlist** of ERC-20 stables per deploy.
3. **Create goal** = deploy blueprint clone **+ mint ERC-721** to creator in one call.
4. Goal actions authorized by **NFT ownership** (not a stored `saver` address alone).
5. **Deposit** anytime (flexible size ≥ min).
6. **Complete** (free) iff `principal >= target`.
7. **Early exit** (all-or-nothing) if under target: fee → treasury, rest → NFT owner; goal closed.
8. Penalty: linear from the factory's `START_PENALTY_BPS` (8000) at `start_time` → **0 at** `end_time`. Callers cannot choose the rate.
9. **tokenURI** switches among **static IPFS** metadata packs by goal lifecycle (not onchain dynamic SVG).
10. Yield adapter optional; v1 may ship with vault = `empty(address)`.



## Non-goals

- Partial early withdraw  
- Monthly deposit enforcement onchain  
- Yield to the saver  
- Cross-chain / bridging  
- Custom `IERC20` / `IERC4626` `.vy` interface files (use Vyper built-ins)  
- Fully dynamic/onchain-rendered NFT art  
- Solidity or Foundry in this repo  
- Frontend (`payday-web`)

---



## Locked protocol rules


| Rule        | Spec                                                                                  |
| ----------- | ------------------------------------------------------------------------------------- |
| Custody     | Goal contract holds (or controls) principal                                           |
| Create      | `create_from_blueprint` for each `PaydayGoal`                                         |
| Access      | **ERC-721 on the factory**; holder of `token_id` controls that goal                   |
| Soulbind    | NFT owner may **disable transfers** for their `token_id` (**irreversible** soulbound) |
| Model       | One goal = one NFT = one asset                                                        |
| Free unlock | `principal >= target` → 100% to NFT owner                                             |
| Early exit  | Only when `principal < target`; closes goal                                           |
| Penalty     | `fee = principal * penalty_bps(now) / 10_000` → `treasury`                            |
| Deposits    | No calendar checks                                                                    |
| Yield       | Optional; surplus → treasury; principal stays nominal                                 |
| Interfaces  | Vyper **built-in** `IERC20Compatible` / `IERC4626` (see below)                        |




### Penalty formula

```
# now in [start_time, end_time):
penalty_bps = START_PENALTY_BPS * (end_time - now) // (end_time - start_time)
# now <= start_time: START_PENALTY_BPS (8000, set by the factory)
# now >= end_time: 0
```

Fee rounds **down** (favor saver). Mul before div.

### Goal lifecycle ↔ NFT metadata (static IPFS)

Not a dynamic NFT. `tokenURI` returns one of three **pre-pinned** immutable pack URIs according to the goal's lifecycle:


| State        | When                                            | tokenURI meaning                                                                                                                             |
| ------------ | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `Created`    | Mint / goal deployed, `principal == 0`          | Default “new goal” metadata + image                                                                                                          |
| `InProgress` | First successful `deposit` (or `principal > 0`) | “Saving” metadata + image                                                                                                                    |
| `Completed`  | `complete()` or `early_exit()` (closed)         | Terminal metadata + image (optionally distinct art for success vs early exit — **v1: one Completed pack is enough**; split later if desired) |


Implementation notes:

- Use **snekmate ERC721** as the base. The factory defines `tokenURI` and does not store a per-token URI.
- Store three immutable URI strings on the factory, `URI_CREATED`, `URI_IN_PROGRESS`, and `URI_COMPLETED` (full `ipfs://…/metadata.json`), set only in the constructor.
- `tokenURI` reads the linked goal: closed → Completed; else `principal > 0` → InProgress; else Created. **No** per-tx SVG generation.
- Transfer of the NFT transfers control of the goal (deposit / complete / early_exit). Document that clearly.



### Irreversible soulbind (per token)

- NFT **owner** may call e.g. `disable_transfers(token_id)` / `soulbind(token_id)` on the factory.
- Only the current owner; only if not already soulbound; `token_id` must exist and belong to them.
- Sets a permanent flag (`transfers_disabled[token_id] = True`). **Cannot be cleared** — no owner escape hatch, no factory admin override in v1.
- While flagged: all `transferFrom` / `safeTransferFrom` (and approve-to-transfer paths) for that id **revert**. Approvals may be cleared or rejected on set.
- Deposit / complete / early_exit still work for the (now fixed) owner.
- Emit `TransfersDisabled(token_id, owner)`.
- Optional: bump `tokenURI` is **not** required for soulbind (lifecycle URIs unchanged unless you add a fourth pack later — **v1: no URI change on soulbind**).

---



## Defaults / caps (factory)


| Param                          | Default                                      |
| ------------------------------ | -------------------------------------------- |
| `START_PENALTY_BPS`            | 8000 (80%), factory-fixed on every new goal  |
| Min duration                   | 30 days                                      |
| Max duration                   | 730 days                                     |
| Min target / min deposit       | per-asset dust in config                     |


Treasury: set at factory deploy. Allowlist: v1 owner-managed `set_asset_allowed` OK.

---



## Interfaces (Vyper built-in — do not vendored copies)

Use Vyper’s built-in interfaces ([docs](https://docs.vyperlang.org/en/stable/interfaces.html#built-in-interfaces)):

- ERC-20: built-in `IERC20Compatible` (or current docs name for ERC20-compatible) for `transfer` / `transferFrom` / `approve` / `balanceOf`
- ERC-4626: built-in `IERC4626` for phase-3 vault park/skim

**Do not** add `interfaces/IERC20.vy` or `interfaces/IERC4626.vy` to the repo unless a gap in the Vyper version forces it — prefer upgrading Vyper/Moccasin instead.

---



## Module layout (Moccasin)

```
payday-core/
  moccasin.toml
  src/
    payday_factory.vy      # ERC-721 (snekmate) + factory + URI state machine
    payday_goal.vy         # blueprint implementation
  tests/
  scripts/                 # deploy blueprint + factory; pin URI strings
  deployments/
  README.md
  DESIGN_BRIEF.md
```

No custom ERC20/4626 interface files.

### Blueprint deploy flow

1. Compile/deploy `PaydayGoal` **as a blueprint** (EIP-5202 / Vyper blueprint bytecode).
2. Factory stores `goal_blueprint: address`.
3. `create_goal(...)` calls Vyper `[create_from_blueprint](https://docs.vyperlang.org/en/stable/built-in-functions.html#create_from_blueprint)` with init args, then mints NFT.



### `payday_factory.vy` (ERC-721 + factory)

- Inherits / uses **snekmate ERC721** (name/symbol e.g. `Payday Goal` / `PAYDAY`).  
- Asset allowlist; duration caps; factory-fixed penalty; `treasury`; `goal_blueprint`.  
- URI slots: `URI_CREATED`, `URI_IN_PROGRESS`, `URI_COMPLETED` (immutable, constructor only).
- Admin ownership is snekmate `ownable_2step` (`transfer_ownership` then `accept_ownership`).  
- Mappings: `token_id → goal`, `goal → token_id` (and/or encode token_id sequentially).

`create_goal(asset, target, end_time, vault=empty(address)) -> (goal: address, token_id: uint256)`

1. Validate asset allowlisted; duration caps.
2. `goal = create_from_blueprint(..., start_penalty_bps=START_PENALTY_BPS, ...)` — the factory always passes 8000. Callers do not supply a penalty.
3. Mint ERC-721 `token_id` to `msg.sender`.
4. `tokenURI` returns the **Created** pack while `principal == 0` and the goal is open.
5. Emit `GoalCreated(goal, token_id, creator, asset, target, …)`.

**Access helper (for goals):** `owner_of_goal(goal) -> address` via `owner_of(token_id)`.

**URI:** no setters. `tokenURI` follows `closed` and `principal` on the linked goal.

### `payday_goal.vy` (blueprint)

Init/immutables: `factory`, `asset`, `treasury`, `target`, `start_time`, `end_time`, `start_penalty_bps`, `token_id`.

State: `principal`, `closed`, optional vault.

**Auth:** for `deposit` / `complete` / `early_exit`, require `msg.sender == ERC721(factory).ownerOf(token_id)` (via factory interface / extensible ERC721). Do **not** key auth off a frozen creator address — NFT transfer moves control.


| Fn                                   | Behavior                                                                                                                |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `deposit(amount)`                    | NFT owner; `IERC20Compatible.transferFrom`; `principal += amount`; on first deposit notify factory → **InProgress** URI |
| `penalty_bps() -> uint256`           | view                                                                                                                    |
| `preview_early_exit() -> (fee, net)` | view                                                                                                                    |
| `complete()`                         | NFT owner; not closed; `principal >= target`; pay principal to owner; close; factory → **Completed** URI                |
| `early_exit()`                       | NFT owner; not closed; `principal < target`; fee→treasury, net→owner; close; factory → **Completed** URI                |
| `skim_yield()`                       | phase 3                                                                                                                 |


Events: `Deposit`, `Completed`, `EarlyExit` (fee, net, penalty_bps).

### Yield (phase 3)

- Optional `vault` as built-in `IERC4626`  
- Nominal principal; skim surplus → treasury  
- NAV < principal → pause deposits + block skim  
- **v1:** `empty(address)` vault

---



## Tests (required)


| ID  | Case                                                                       |
| --- | -------------------------------------------------------------------------- |
| T1  | `create_goal` deploys via blueprint + mints NFT to creator                 |
| T2  | deposit as NFT owner increases principal; URI → InProgress                 |
| T3  | non-owner cannot deposit/complete/exit                                     |
| T4  | after NFT transfer, new owner can deposit; old cannot                      |
| T5  | complete when `principal >= target`; URI → Completed                       |
| T6  | complete reverts when under target                                         |
| T7  | early exit mid-curve — fee math + treasury ↑; URI → Completed              |
| T8  | early exit at/after `end_time` — fee 0                                     |
| T9  | early exit reverts when `principal >= target`                              |
| T10 | non-allowlisted asset cannot create                                        |
| T11 | duration caps enforced; factory sets the 80% penalty                       |
| T12 | closed goal rejects further deposit/exit                                   |
| T13 | `tokenURI` is Created at mint; not snekmate default after state set        |
| T14 | owner `disable_transfers` → transfer reverts; deposit still works          |
| T15 | `disable_transfers` cannot be undone; second call reverts or no-ops safely |
| T16 | non-owner cannot soulbind                                                  |


---



## Do / don’t

**Do**

- Vyper built-in IERC20/IERC4626 interfaces  
- `create_from_blueprint` for goals  
- Factory = ERC-721 access pass + URI state machine  
- Static IPFS metadata packs per lifecycle

**Don’t**

- Hand-rolled `interfaces/IERC20.vy` / `IERC4626.vy`  
- Auth only on immutable creator (ignore NFT)  
- Onchain dynamic NFT rendering for v1  
- Foundry/Solidity dual-stack  
- Lower `target` after create  
- Enforce monthly deposits  
- Re-enable transfers after soulbind  
- Admin unlock of soulbound tokens in v1

---



## Phased build

1. Blueprint `PaydayGoal` + Factory ERC-721 create/mint + URI slots (pure lock)
2. Tests T1–T16
3. Optional ERC-4626 park + skim
4. Deploy scripts + `deployments/<chain>.json` + document IPFS CIDs



## Acceptance

- [ ] Goals only via `create_from_blueprint`  
- [ ] Factory is ERC-721; mint on create; owner gates goal actions  
- [ ] URI updates Created → InProgress → Completed from IPFS packs  
- [ ] No custom IERC20/4626 interface files  
- [ ] Penalty + access tests green under Moccasin  
- [ ] README: blueprint deploy, URI pins, param table  
- [ ] Per-token irreversible transfer disable (soulbind) works; cannot revert  



## Handoff

Web: `../web/DESIGN_BRIEF.md` — list goals by NFT balance / transfers; show lifecycle art from `tokenURI`.