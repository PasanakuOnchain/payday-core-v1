# Moccasin Vyper-Native Testing

Prefer Moccasin-native APIs over raw Titanoboa unless the API is unavailable.

Sources:
- [Moccasin testing](https://cyfrin.github.io/moccasin/core_concepts/testing.html)
- [Titanoboa native import syntax](https://titanoboa.readthedocs.io/en/latest/guides/scripting/native_import_syntax/)
- [Moccasin named contracts](https://cyfrin.github.io/moccasin/core_concepts/named_contracts.html)

## Project layout

```
project/
├── moccasin.toml
├── pyproject.toml
├── .coveragerc              # plugins = boa.coverage
├── src/
│   ├── factory.vy
│   └── collection.vy
├── script/
│   ├── deploy.py            # moccasin_main() for mox run deploy
│   └── mocks/               # named-contract deploy scripts (optional)
│       └── deploy_feed.py
└── tests/
    ├── conftest.py
    ├── mocks/
    │   ├── MockERC20.vy
    │   └── deployers.py
    ├── utils/
    │   └── protocols.py
    └── unitary/
        └── factory/
            └── test_deploy_collection.py
```

## Native import syntax

Moccasin auto-wraps contracts under `src/` as importable Python modules. Internally uses `importlib` + `boa.load_partial`.

```python
from src import collection, factory
from moccasin.boa_tools import VyperContract

# Deploy — constructor syntax
blueprint: VyperContract = collection.deploy_as_blueprint()
deployed: VyperContract = factory.deploy(blueprint.address)

# Call externals as Python methods
collection_id = factory.deploy_collection("ipfs://base", "ipfs://meta")

# Re-bind to existing address
instance: VyperContract = collection.at(deployed_address)
```

Note: `import boa` must be loaded first for native imports. Moccasin handles this during `mox test` / `mox run`.

## Running tests

| Command | Purpose |
|---------|---------|
| `mox test` | Compile + run all pytest tests |
| `mox test -n auto` | Parallel via pytest-xdist |
| `pytest tests/test_foo.py::test_bar -v` | Single test |
| `pytest tests/ --gas-profile` | Gas profiling |

Moccasin bundles pytest plugins: `titanoboa`, `hypothesis`, `cov`.

### Coverage

`.coveragerc`:

```ini
[run]
plugins = boa.coverage
```

## conftest + shared deploy

DRY between `mox run deploy` and tests:

```python
# script/deploy.py
from src import collection, factory
from moccasin.boa_tools import VyperContract

def deploy() -> VyperContract:
    blueprint = collection.deploy_as_blueprint()
    return factory.deploy(blueprint.address)

def moccasin_main() -> VyperContract:
    return deploy()
```

```python
# tests/conftest.py
import pytest
from script.deploy import deploy

@pytest.fixture(scope="module")
def factory_contract():
    return deploy()
```

## Blueprint / factory pattern

For factory-deployed contracts (e.g. `create_from_blueprint`):

```python
from src import collection, factory

@pytest.fixture(scope="module")
def collection_blueprint():
    return collection.deploy_as_blueprint()

@pytest.fixture(scope="module")
def factory_contract(collection_blueprint):
    return factory.deploy(collection_blueprint.address)

@pytest.fixture(scope="module")
def deployed_collection(factory_contract):
    collection_id = factory_contract.deploy_collection("ipfs://base", "ipfs://meta")
    addr = factory_contract.collections(collection_id)
    return collection.at(addr)
```

## Named contracts + fork networks

Declare in `moccasin.toml`:

```toml
[networks.mainnet-fork]
url = "https://ethereum-rpc.publicnode.com"
chain_id = 1
fork = true

[networks.mainnet-fork.contracts.usdc]
address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
abi = "ERC20.vy"
# abi_from_explorer = true  # alternative
```

Use in tests/scripts:

```python
from moccasin.config import get_config
from moccasin.boa_tools import VyperContract

def test_against_usdc():
    network = get_config().get_active_network()
    usdc: VyperContract = network.manifest_named("usdc")
    assert usdc.decimals() == 6
```

For local mocks with deploy-on-first-use:

```toml
[networks.pyevm.contracts.price_feed]
deployer_script = "script/mocks/deploy_price_feed.py"
```

```python
# script/mocks/deploy_price_feed.py
from tests.mocks.deployers import MOCK_ORACLE
from moccasin.boa_tools import VyperContract

def moccasin_main() -> VyperContract:
    return MOCK_ORACLE.deploy(18, 3000 * 10**18)
```

Script **must** return `VyperContract` or `ZksyncContract`.

## Mocks — `tests/mocks/`

Mocks live outside `src/` — load via `boa.load_partial`:

```python
# tests/mocks/deployers.py
import boa

MOCK_ERC20 = boa.load_partial("tests/mocks/MockERC20.vy")
MOCK_ORACLE = boa.load_partial("tests/mocks/MockOracle.vy")
```

```python
# tests/conftest.py
from tests.mocks.deployers import MOCK_ERC20

@pytest.fixture(scope="module")
def mock_token():
    return MOCK_ERC20.deploy(18)
```

Rules:
- `.vy` mocks in `tests/mocks/` — typed, compilable, reusable
- Deployer constants in `tests/mocks/deployers.py`
- Production deployers stay in `tests/utils/deployers.py`
- Avoid inline `boa.loads` except prototypes

## When to drop to raw `import boa`

| Need | API |
|------|-----|
| Mocks outside `src/` | `boa.load_partial("tests/mocks/Foo.vy")` |
| Internal state read | `contract.eval("self.field")` |
| Test isolation | `with boa.env.anchor():` |
| Storage manipulation | `boa.env.set_storage(addr, slot, value)` |
| Token balance | `boa.deal(token, addr, amount)` |
| ETH balance | `boa.env.set_balance(addr, amount)` |
| Time travel | `boa.env.time_travel(seconds=N)` |
| Fast mode | `boa.env.enable_fast_mode()` in conftest |
| Fork | `boa.fork(url, block_identifier=N)` |

## moccasin.toml essentials

```toml
[project]
src = "src"
out = "out"
dependencies = ["snekmate"]

[networks.pyevm]
is_zksync = false

[networks.anvil]
url = "http://127.0.0.1:8545"
chain_id = 31337
```

- `pyevm` — in-process local network (default for tests)
- `anvil` — external Anvil for live scripting
- Fork networks — `fork = true` + contract addresses

## Type hints

Always type contract handles:

```python
from moccasin.boa_tools import VyperContract

def deploy() -> VyperContract:
    ...
```
