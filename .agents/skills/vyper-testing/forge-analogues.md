# Foundry → Titanoboa Cheatcode Map

Reference for developers migrating from Foundry/Forge to Titanoboa/Moccasin.

Source: [Titanoboa Forge analogues](https://titanoboa.readthedocs.io/en/latest/guides/forge/)

## Environment setup

| Forge | Titanoboa / Moccasin |
|-------|---------------------|
| `forge init my-project` | `mox init` or manual project with `moccasin.toml` |
| `forge install` | `mox install ORG/REPO` (Vyper deps in `moccasin.toml`) |

## Running tests

| Forge | Titanoboa / Moccasin |
|-------|---------------------|
| `forge test` | `pytest tests/` or `mox test` |
| `forge test --match-test testFoo` | `pytest tests/test_file.py::test_foo` |
| `forge test --match-contract TestContract` | `pytest tests/test_contract.py` |
| `forge test -vvvv` | `pytest tests/ -v` |
| Parallel tests | `mox test -n auto` (pytest-xdist) |
| Gas report | `pytest tests/ --gas-profile` |

## Contract deployment

| Forge | Titanoboa / Moccasin |
|-------|---------------------|
| `new MyContract()` | `MyContract()` via native import, or `DEPLOYER.deploy()` |
| `new MyContract{value: 1 ether}(arg1, arg2)` | `MyContract(arg1, arg2, value=10**18)` |
| Blueprint / clone | `DEPLOYER.deploy_as_blueprint()` + `create_from_blueprint` |

## Pranking (impersonating addresses)

| Forge | Titanoboa |
|-------|-----------|
| `vm.prank(alice); contract.withdraw();` | `contract.withdraw(sender=alice)` |
| `vm.startPrank(alice); ... vm.stopPrank();` | `with boa.env.prank(alice): ...` |

## Balances

| Forge | Titanoboa |
|-------|-----------|
| `vm.deal(alice, 100 ether)` | `boa.env.set_balance(alice, 100 * 10**18)` |
| ERC20 mint in test | `boa.deal(token, alice, amount)` |

## Time and blocks

| Forge | Titanoboa |
|-------|-----------|
| `vm.warp(block.timestamp + 1 days)` | `boa.env.time_travel(seconds=86400)` |
| `skip(1 days)` | `boa.env.time_travel(seconds=86400)` |
| `vm.roll(block.number + 100)` | `boa.env.time_travel(blocks=100)` |

## Forking

| Forge | Titanoboa / Moccasin |
|-------|---------------------|
| `forge test --fork-url URL` | `boa.fork("URL")` |
| `forge test --fork-url URL --fork-block-number N` | `boa.fork("URL", block_identifier=N)` |
| Fork network in config | `fork = true` in `moccasin.toml` network section |

## Expecting reverts

| Forge | Titanoboa |
|-------|-----------|
| `vm.expectRevert("Insufficient balance"); token.transfer(...);` | `with boa.reverts("Insufficient balance"): token.transfer(...)` |
| `vm.expectRevert();` | `with boa.reverts():` |
| Dev revert string | `with boa.reverts(dev="Exact dev message"):` |

## Storage manipulation

| Forge | Titanoboa |
|-------|-----------|
| `vm.store(addr, slot, value)` | `boa.env.set_storage(addr, slot, value)` |
| `vm.load(addr, slot)` | `boa.env.get_storage(addr, slot)` |

## Snapshots / checkpoints

| Forge | Titanoboa |
|-------|-----------|
| `uint256 snap = vm.snapshot(); ... vm.revertTo(snap);` | `with boa.env.anchor(): ...` (auto-reverts after block) |

## Event testing

| Forge | Titanoboa |
|-------|-----------|
| `vm.expectEmit(...); emit Transfer(...); token.transfer(...);` | `token.transfer(...); logs = token.get_logs(); assert logs[0].event_type.name == "Transfer"` |

## Mock contracts

| Forge | Titanoboa |
|-------|-----------|
| Solidity mock contract | `tests/mocks/MockToken.vy` + `boa.load_partial(...)` |
| Inline mock | `boa.loads("""@external def mint(...): ...""")` (discouraged — use `tests/mocks/`) |

## Fuzzing

| Forge | Titanoboa |
|-------|-----------|
| `function testFuzz(uint256 amount) { vm.assume(...); }` | `@given(amount=st.integers(min_value=1, max_value=10**21))` (Hypothesis) |

## Script deployment

| Forge | Titanoboa / Moccasin |
|-------|---------------------|
| `script/Deploy.s.sol` with `run()` | `script/deploy.py` with `moccasin_main() -> VyperContract` |
| `forge script` | `mox run deploy` or `mox run script/deploy.py` |

## Setup pattern

**Forge:**

```solidity
function setUp() public {
    contract = new MyContract();
    vm.deal(alice, 100 ether);
}
```

**Titanoboa:**

```python
@pytest.fixture
def contract():
    return MyContract()

@pytest.fixture
def alice():
    addr = boa.env.generate_address("alice")
    boa.env.set_balance(addr, 100 * 10**18)
    return addr
```

## Key differences

1. **Language**: Forge tests in Solidity; Titanoboa tests in Python
2. **Contract language**: Forge targets Solidity; Titanoboa targets Vyper
3. **Test runner**: Forge built-in; Titanoboa uses pytest
4. **State management**: Forge `vm` cheatcodes; Titanoboa context managers (`with`)
5. **Deployment**: Forge `new`; Titanoboa native import or `DEPLOYER.deploy()`

## Best practices migration

- Replace Forge scripts with Python scripts using Titanoboa/Moccasin
- Use pytest fixtures instead of `setUp()`
- Use context managers (`with`) for state changes
- Leverage Hypothesis for fuzzing, pytest-xdist for parallelism
- Use `boa.env.anchor()` for test isolation instead of manual snapshots
