# Curve Finance Test Patterns

Production-grade Vyper test conventions from [curve-stablecoin/tests](https://github.com/curvefi/curve-stablecoin/tree/master/tests).

Curve is migrating from semantic folders (`controller/`, `lending/`) toward a structured layout (`unitary/`, `integration/`, `fuzz/`, `forked/`). Follow the **target layout** for new tests.

## Directory structure

```
tests/
├── conftest.py              # shared fixtures, hypothesis profiles
├── unitary/
│   └── controller/
│       └── test_create_loan.py
├── integration/
├── forked/
├── fuzz/
├── mocks/                   # preferred for Moccasin projects
│   ├── MockERC20.vy
│   └── deployers.py
└── utils/
    ├── deployers.py         # production contract deployers
    ├── protocols.py         # full protocol deployment class
    ├── constants.py         # MAX_UINT256, MIN_TICKS, etc.
    └── __init__.py          # helpers: max_approve, filter_logs
```

## Deployers pattern

Centralize production contract loading in `tests/utils/deployers.py`:

```python
import boa
from vyper.compiler.settings import OptimizationLevel

compiler_args_default = {"experimental_codegen": False}
compiler_args_codesize = {
    **compiler_args_default,
    "optimize": OptimizationLevel.CODESIZE,
}
compiler_args_gas = {
    **compiler_args_default,
    "optimize": OptimizationLevel.GAS,
}

AMM_DEPLOYER = boa.load_partial(
    BASE_PATH / "AMM.vy", compiler_args=compiler_args_codesize
)
ERC20_MOCK_DEPLOYER = boa.load_partial(
    TESTING_PATH / "ERC20Mock.vy", compiler_args=compiler_args_default
)
```

Rules:
- Match `#pragma optimize codesize` → `compiler_args_codesize`
- Match `#pragma optimize gas` → `compiler_args_gas`
- Export as module-level `*_DEPLOYER` constants
- Use `.deploy()`, `.at(address)`, `.deploy_as_blueprint()`

## Protocol class

For multi-contract systems, use `tests/utils/protocols.py`:

```python
class Llamalend:
    def __init__(self):
        self.admin = boa.env.generate_address("admin")
        self.blueprints = Blueprints(amm=AMM_DEPLOYER, ...)
        self.__init_mint_markets(initial_price)

    def create_mint_market(self, collateral_token, ...) -> dict:
        self.mint_factory.add_market(..., sender=self.admin)
        return {
            "controller": self._mint_controller_deployer.at(controller_address),
            "amm": AMM_DEPLOYER.at(amm_address),
        }
```

- Deploy blueprints in `__init__`
- Expose `create_*()` factory methods returning dicts of named handles
- Admin actions via `sender=self.admin`

## conftest.py fixtures

```python
from datetime import timedelta
import boa
import pytest
from hypothesis import settings, Phase

boa.env.enable_fast_mode()

no_shrink = settings.register_profile(
    "no-shrink",
    phases=list(Phase)[:4],
    deadline=timedelta(seconds=1000),
)
settings.load_profile("no-shrink")

@pytest.fixture(scope="module")
def proto():
    return Llamalend()

@pytest.fixture(scope="module")
def admin(proto):
    return proto.admin

@pytest.fixture(scope="module", params=["mint", "lending"])
def market_type(request):
    return request.param

@pytest.fixture(scope="module", params=[2, 18])
def collateral_decimals(request):
    return request.param
```

Fixture scoping:
- `scope="module"` — protocol, markets, tokens (expensive)
- `scope="session"` — deployer constants
- `params=[...]` — parametrize decimals, market types, branches

Deprecated in Curve: generic `alice`/`accounts` fixtures — use role-named addresses inline.

## Test body structure

From `tests/unitary/controller/test_create_loan.py`:

```python
@pytest.mark.parametrize("different_creator", [True, False])
def test_create_loan(controller, amm, borrowed_token, collateral_token, amounts):
    """
    Test loan creation using wallet collateral.
    Money Flow: collateral (creator) → AMM
               debt (Controller) → Borrower
    """
    borrower = boa.env.eoa

    # ================= Capture initial state =================
    assert controller.n_loans() == 0

    # ================= Setup tokens =================
    boa.deal(collateral_token, creator, amounts["collateral"])
    max_approve(collateral_token, controller, sender=creator)

    # ================= Execute loan creation =================
    controller.create_loan(..., sender=creator)

    # ================= Verify position state =================
    assert controller.loan_exists(borrower)
    assert controller.health(borrower) == pytest.approx(preview_health, rel=1e-10)

    # ================= Verify logs =================
    borrow_logs = filter_logs(controller, "Borrow")
    assert borrow_logs[0].user == borrower

    # ================= Verify money flows =================
    assert borrowed_to_borrower == amounts["debt"]
    assert collateral_to_amm == amounts["collateral"]
```

Key techniques:
- Docstring describes money flow
- Section comments (`# ====`) separate phases
- `sender=` sets msg.sender
- `pytest.approx(..., rel=1e-10)` for fixed-point math
- `contract.eval("self.field")` for internal state
- Snapshot helpers for balance deltas
- `@pytest.mark.parametrize` for branch coverage

## Helper utilities

Common helpers in `tests/utils/__init__.py`:

```python
def max_approve(token, spender, sender):
    token.approve(spender, 2**256 - 1, sender=sender)

def filter_logs(contract, event_name: str):
    return [log for log in contract.get_logs() if log.event_type.name == event_name]
```

Constants in `tests/utils/constants.py`:

```python
MAX_UINT256 = 2**256 - 1
MIN_TICKS = 4
MAX_TICKS = 50
```

## Revert tests

```python
def test_create_loan_already_exists(controller, collateral_token, amounts):
    borrower = boa.env.eoa
    boa.deal(collateral_token, borrower, amounts["collateral"])
    controller.create_loan(..., sender=borrower)

    with boa.reverts("Loan already created"):
        controller.create_loan(..., sender=borrower)
```

Use `boa.reverts(dev="...")` for `@dev` revert strings.

## Hypothesis fuzzing

Register profiles in conftest, use in `tests/fuzz/`:

```python
from hypothesis import given, strategies as st

@given(amount=st.integers(min_value=1, max_value=10**21))
def test_withdraw_fuzz(vault, amount):
    ...
```

## Mocks in Curve vs Moccasin projects

Curve keeps mocks in `curve_stablecoin/testing/` inside the package. For Moccasin projects, colocate mocks under `tests/mocks/` instead — see [moccasin-patterns.md](moccasin-patterns.md).
