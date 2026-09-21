---
name: vyper-best-practices
description: >
  Vyper smart contract best practices, naming conventions, and module patterns derived from
  snekmate and the official Vyper documentation. Use when writing, reviewing, or refactoring
  Vyper contracts (.vy files), creating Vyper modules, or when the user asks about Vyper
  coding standards, contract layout, NatSpec, decorator order, or security patterns.
---

# Vyper Best Practices

## Quick Start

Apply this skill whenever you are:

- Writing or editing `.vy` files
- Reviewing or refactoring Vyper smart contracts
- Creating Vyper modules or interfaces (`.vyi`)
- Answering questions about Vyper conventions

Core principle: Vyper favours **composition over inheritance**. Reuse code via modules, not class hierarchies.

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Module/mock files | snake_case `.vy` | `my_module.vy`, `ownable_mock.vy` |
| Interface files | PascalCase with `I` prefix `.vyi` | `IMyInterface.vyi` |
| Functions, params, state vars | snake_case | `transfer_ownership`, `new_owner` |
| `constant` / `immutable` | SCREAMING_SNAKE_CASE | `MAX_SUPPLY`, `FACTORY_ADDRESS` |
| Internal items | underscore prefix | `_check_owner`, `_balances`, `_CACHED_DOMAIN_SEPARATOR` |

Internal `constant`, `immutable`, state variables, and functions **must** have an underscore prefix:

```vyper
_SUPPORTED_INTERFACES: constant(bytes4[1]) = [0x01FFC9A7]

_CACHED_DOMAIN_SEPARATOR: immutable(bytes32)

_balances: HashMap[uint256, HashMap[address, uint256]]

@internal
@pure
def _as_singleton_array(element: uint256) -> DynArray[uint256, 1]:
    return [element]
```

## Contract Layout Order

Maintain this top-to-bottom order in every `.vy` file. Separate each top-level declaration with **two blank lines**.

1. **Pragmas** (one per line, in this order):
   - `# pragma version ~=0.4.3`
   - `# pragma evm-version <version>` (if applicable)
   - `# pragma optimize <mode>` (if applicable)
   - `# pragma nonreentrancy <on|off>` (if applicable)
   - `# pragma experimental-codegen` (if applicable)
2. **Contract-level docstring** (`@title`, `@license`, `@author`, etc.)
3. **Built-in interface imports** (e.g. `from ethereum.ercs import IERC165`)
   - `implements:` on the next line if applicable
4. **Custom interface imports**
   - `implements:` on the next line if applicable
5. **Module imports** (with aliases)
   - `initializes:` or `uses:` on the next line if applicable
6. **Module `exports`**
7. **Public constants**, then **internal constants**
8. **Public immutables**, then **internal immutables**
9. **`flag` definitions**
10. **`struct` definitions**
11. **Public state variables**, then **internal state variables**
12. **`event` declarations**
13. **`__init__` function**, then **`__default__` function**
14. **External functions**
15. **Internal functions**

## Decorator Order

When a function uses multiple decorators, apply them in this exact order:

1. **Visibility**: `@external`, `@internal`, or `@deploy`
2. **Mutability**: `@pure`, `@view`, or `@payable` (omit `@nonpayable` — it is the default)
3. **Nonreentrancy**: `@nonreentrant`
4. **Raw return**: `@raw_return`

```vyper
@external
@payable
@nonreentrant
def deposit():
    ...

@external
@view
def get_balance(account: address) -> uint256:
    ...

@internal
@pure
def _compute_hash(data: bytes32) -> bytes32:
    ...
```

## Modules

Vyper modules are the primary mechanism for code reuse. Every `.vy` file is a valid module.

### Importing and initializing

```vyper
from snekmate.auth import ownable as ow
initializes: ow

@deploy
@payable
def __init__():
    ow.__init__()
```

- Use `initializes:` when your contract owns the module's state and calls its `__init__()`.
- Use `uses:` when you access the module's state but defer initialization to a parent contract.

### Dependencies (walrus syntax)

When a module itself `uses` another module, declare the dependency explicitly:

```vyper
from snekmate.auth import ownable as ow
from snekmate.tokens import erc721
initializes: ow
initializes: erc721[ownable := ow]
```

### Exporting functions

External functions from modules are **not** automatically exposed. Export explicitly:

```vyper
exports: ow.__interface__

exports: erc721.__interface__

exports: (
    ed.eip712Domain,
    ow.transfer_ownership,
)
```

## Security

- **Reentrancy protection**: Use `@nonreentrant` on any external function that makes external calls, or enable `# pragma nonreentrancy on` at the file level.
- **Explicit external calls**: Use `extcall` for state-changing calls, `staticcall` for read-only calls (Vyper 0.4+).
- **Bounded loops**: Vyper enforces bounded iteration. Always provide compile-time bounds via `range(STOP)` or `range(stop, bound=N)`.
- **Overflow safety**: Vyper checks arithmetic by default. If you bypass checks, add comments explaining why overflow/underflow cannot occur.
- **Access control**: Use snekmate's `ownable` or `access_control` modules rather than hand-rolling checks.
- **Constructor pattern**: Mark `__init__` as `@deploy @payable` to omit `msg.value` check opcodes (saves gas in creation bytecode).

## NatSpec Documentation

### Contract-level (in the module docstring)

```vyper
"""
@title Owner-Based Access Control Functions
@custom:contract-name ownable
@license MIT
@author Your Name
@notice Brief user-facing description.
@dev Detailed developer notes.
"""
```

### Function-level

Every function should include full NatSpec with `@dev`, `@notice` (if applicable), `@param` for each parameter, and `@return` if a value is returned:

```vyper
@external
def transfer(to: address, amount: uint256) -> bool:
    """
    @dev Transfers `amount` tokens from the caller to `to`.
    @notice Transfers tokens to the given address.
    @param to The recipient address.
    @param amount The number of tokens to transfer.
    @return True on success.
    """
    ...
```

## Code Style

- **Line length**: max 120 characters for code; max 80 characters for comments (URLs excepted).
- **Blank lines**: two blank lines between every top-level declaration (imports, constants, state vars, events, functions).
- **Numeric literals**: use underscores as thousand separators (`1_000_000` not `1000000`).
- **Assertions**: prefer descriptive revert messages: `assert condition, "ownable: caller is not the owner"`.
- **Unchecked arithmetic**: if Vyper's default bounds/overflow checks are disabled for a section, add a comment explaining the safety invariant.
- For any undocumented behaviour, follow [Vyper's Style Guide](https://docs.vyperlang.org/en/latest/style-guide.html) or [PEP 8](https://peps.python.org/pep-0008).

## Blueprint / Factory Pattern

When deploying contracts from blueprints (ERC-5202):

```vyper
BLUEPRINT: immutable(address)

@deploy
@payable
def __init__(blueprint_: address):
    BLUEPRINT = blueprint_

@external
def create_child(name_: String[25], symbol_: String[5]) -> address:
    child: address = create_from_blueprint(
        BLUEPRINT,
        name_,
        symbol_,
    )
    return child
```

- Store the blueprint address as an `immutable`.
- Pass constructor arguments positionally to `create_from_blueprint`.
- Emit an event after creation for off-chain indexing.

## Additional Resources

- For detailed conventions, see [reference.md](reference.md)
- snekmate: <https://github.com/pcaversaccio/snekmate>
- Vyper docs: <https://docs.vyperlang.org>
- Vyper modules: <https://docs.vyperlang.org/en/latest/using-modules.html>
- NatSpec: <https://docs.vyperlang.org/en/latest/natspec.html>
