---
name: vyper-testing
description: Write Vyper smart contract tests with Titanoboa and Moccasin following Curve Finance patterns. Use when writing or extending tests for .vy contracts, mox test, pytest, native import from src, deploy_as_blueprint, tests/mocks, manifest_named, conftest fixtures, or when the user asks for Vyper test coverage.
---

# Vyper Testing (Titanoboa + Moccasin)

Write Vyper contract tests using pytest + Titanoboa, following Curve Finance patterns. For Moccasin projects, prefer Vyper-native APIs (`from src import ...`, `deploy_as_blueprint`, named contracts) over raw `boa` calls.

## Workflow

Copy this checklist and track progress:

```
Task Progress:
- [ ] Read contract under test (.vy), NatSpec, CONTEXT.md / architecture docs
- [ ] Classify test type (unitary / integration / forked / fuzz)
- [ ] Check existing conftest.py and deploy helpers — extend, don't duplicate
- [ ] Add mocks to tests/mocks/ if needed (not inline boa.loads)
- [ ] Write test(s) — one behavior per function, Curve-style sections
- [ ] Run mox test (Moccasin) or pytest tests/ -v (raw Titanoboa)
- [ ] Fix failures until green
```

## Test directory layout

| Directory | Purpose |
|-----------|---------|
| `tests/unitary/<contract>/` | Isolated function/behavior tests |
| `tests/integration/` | Multi-contract flows |
| `tests/forked/` | Mainnet fork tests |
| `tests/fuzz/` | Hypothesis property tests |
| `tests/mocks/` | Vyper mock contracts (`.vy`) + mock deployers |
| `tests/utils/` | Production deployers, protocol helpers, constants |
| `tests/conftest.py` | Shared pytest fixtures |
| `script/mocks/` | Moccasin named-contract deploy scripts (optional) |

## Naming conventions

- Files: `test_<behavior>.py`
- Functions: `test_<action>_<condition>`
- Fixtures: domain role nouns (`controller`, `admin`, `collateral_token`) — not generic `alice`/`bob`

## Moccasin vs raw Titanoboa

**Moccasin project** (has `moccasin.toml`):
- Import production contracts: `from src import factory, collection`
- Run: `mox test` or `mox test -n auto`
- Mocks outside `src/`: `boa.load_partial("tests/mocks/MockERC20.vy")`
- See [moccasin-patterns.md](moccasin-patterns.md)

**Raw Titanoboa project** (Curve-style):
- Deployers: `boa.load_partial("path/Contract.vy")` in `tests/utils/deployers.py`
- Run: `pytest tests/ -v`
- See [curve-patterns.md](curve-patterns.md)

## Quick patterns

### Deploy (Moccasin)

```python
from src import collection, factory
from moccasin.boa_tools import VyperContract

blueprint: VyperContract = collection.deploy_as_blueprint()
deployed: VyperContract = factory.deploy(blueprint.address)
instance = collection.at(deployed_address)
```

### Deploy (raw Titanoboa)

```python
AMM_DEPLOYER = boa.load_partial("path/AMM.vy", compiler_args=compiler_args_codesize)
contract = AMM_DEPLOYER.deploy(arg1, arg2)
instance = AMM_DEPLOYER.at(deployed_address)
```

### Access control + revert

```python
with boa.env.prank(unauthorized):
    with boa.reverts("Only owner"):
        contract.owner_function()
```

Or use `sender=` keyword: `contract.foo(sender=admin)`.

### Events

```python
contract.transfer(recipient, amount, sender=holder)
logs = contract.get_logs()
assert len(logs) == 1
assert logs[0].event_type.name == "Transfer"
assert logs[0].args.receiver == recipient
```

### Test body structure (Curve style)

```python
def test_create_loan(controller, collateral_token, amounts):
    """Money Flow: collateral → AMM, debt → borrower."""
    borrower = boa.env.eoa

    # ================= Capture initial state =================
    assert controller.n_loans() == 0

    # ================= Setup =================
    boa.deal(collateral_token, borrower, amounts["collateral"])

    # ================= Execute =================
    controller.create_loan(..., sender=borrower)

    # ================= Verify state, logs, money flows =================
    assert controller.loan_exists(borrower)
```

## Mocks — `tests/mocks/`

- Write mocks as `.vy` files in `tests/mocks/`
- Export deployers from `tests/mocks/deployers.py`
- Keep `tests/utils/deployers.py` for production contracts only
- Avoid inline `boa.loads` except throwaway prototypes

## Fixture scoping

```python
boa.env.enable_fast_mode()  # top of conftest.py

@pytest.fixture(scope="module")
def controller(market, admin):
    ...
```

- `scope="module"` — expensive deployments (protocol, markets)
- `scope="session"` — deployer constants
- `@pytest.fixture(params=[...])` — parametrize decimals, market types

## Foundry migration

If the user comes from Foundry, see [forge-analogues.md](forge-analogues.md) for cheatcode mappings.

## Additional resources

- [forge-analogues.md](forge-analogues.md) — Foundry → Titanoboa cheatcode map
- [curve-patterns.md](curve-patterns.md) — Curve deployers, protocols, fixtures, helpers
- [moccasin-patterns.md](moccasin-patterns.md) — native imports, named contracts, fork networks
- [examples.md](examples.md) — copy-paste templates

## External references

- [Titanoboa Forge analogues](https://titanoboa.readthedocs.io/en/latest/guides/forge/)
- [Titanoboa native import syntax](https://titanoboa.readthedocs.io/en/latest/guides/scripting/native_import_syntax/)
- [Moccasin testing](https://cyfrin.github.io/moccasin/core_concepts/testing.html)
- [Curve curve-stablecoin tests](https://github.com/curvefi/curve-stablecoin/tree/master/tests)
