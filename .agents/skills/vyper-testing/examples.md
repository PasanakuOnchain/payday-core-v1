# Vyper Test Examples

Annotated templates. Moccasin-native style first; raw Titanoboa noted where different.

---

## 1. Unit test — native import deploy + assert

**Moccasin** (`tests/unitary/collection/test_mint.py`):

```python
import boa
from src import collection, factory
from moccasin.boa_tools import VyperContract


def test_mint_increases_balance(deployed_collection, minter):
    """Money Flow: none — mint creates balance from zero."""
    token_id = 1
    amount = 100

    # ================= Capture initial state =================
    assert deployed_collection.balanceOf(minter, token_id) == 0

    # ================= Execute =================
    deployed_collection.mint(minter, token_id, amount, sender=minter)

    # ================= Verify =================
    assert deployed_collection.balanceOf(minter, token_id) == amount
```

**Fixtures** (`tests/conftest.py`):

```python
import pytest
from src import collection, factory


@pytest.fixture(scope="module")
def collection_blueprint():
    return collection.deploy_as_blueprint()


@pytest.fixture(scope="module")
def factory_contract(collection_blueprint):
    return factory.deploy(collection_blueprint.address)


@pytest.fixture(scope="module")
def deployed_collection(factory_contract):
    cid = factory_contract.deploy_collection("ipfs://base", "ipfs://meta")
    return collection.at(factory_contract.collections(cid))


@pytest.fixture
def minter():
    return boa.env.generate_address("minter")
```

**Raw Titanoboa variant** — replace `from src import ...` with:

```python
COLLECTION = boa.load_partial("src/collection.vy")
deployed = COLLECTION.deploy(...)
```

---

## 2. Revert test — access control

```python
import boa


def test_only_minter_can_mint(deployed_collection, unauthorized):
    token_id = 1
    amount = 100

    with boa.env.prank(unauthorized):
        with boa.reverts("Access control: account is missing role"):
            deployed_collection.mint(unauthorized, token_id, amount)


def test_mint_zero_amount_reverts(deployed_collection, minter):
    with boa.reverts("Amount must be > 0"):
        deployed_collection.mint(minter, 1, 0, sender=minter)
```

Use `boa.reverts(dev="Exact @dev message")` when matching Vyper dev strings.

---

## 3. Event test — get_logs assertions

```python
def test_transfer_emits_event(deployed_collection, holder, recipient):
    token_id = 1
    amount = 50
    deployed_collection.mint(holder, token_id, amount, sender=holder)

    # ================= Execute =================
    deployed_collection.transfer(holder, recipient, token_id, amount, sender=holder)

    # ================= Verify logs =================
    logs = deployed_collection.get_logs()
    transfer_logs = [l for l in logs if l.event_type.name == "Transfer"]
    assert len(transfer_logs) == 1
    assert transfer_logs[0].args.sender == holder
    assert transfer_logs[0].args.receiver == recipient
    assert transfer_logs[0].args.id == token_id
    assert transfer_logs[0].args.amount == amount
```

Or use a helper:

```python
from tests.utils import filter_logs

logs = filter_logs(deployed_collection, "Transfer")
assert logs[0].args.amount == amount
```

---

## 4. Blueprint / factory test

Relevant for Factory → Collection via `create_from_blueprint`:

```python
import boa
from src import collection, factory


def test_factory_deploys_collection(factory_contract, collection_blueprint):
    """Money Flow: none — factory creates collection from blueprint."""
    base_uri = "ipfs://base"
    contract_uri = "ipfs://contract"

    # ================= Capture initial state =================
    initial_count = factory_contract.collection_count()

    # ================= Execute =================
    collection_id = factory_contract.deploy_collection(base_uri, contract_uri)
    collection_addr = factory_contract.collections(collection_id)

    # ================= Verify =================
    assert factory_contract.collection_count() == initial_count + 1
    assert collection_addr != boa.util.erc.EMPTY_ADDRESS

    deployed = collection.at(collection_addr)
    assert deployed.base_uri() == base_uri
    assert deployed.contract_uri() == contract_uri

    # Blueprint address unchanged
    assert collection_blueprint.address != collection_addr
```

---

## 5. Mock fixture — tests/mocks/

**Mock contract** (`tests/mocks/MockERC20.vy`):

```vyper
# @version 0.4.1

balances: public(HashMap[address, uint256])
decimals: public(uint256)

@deploy
def __init__(decimals_: uint256):
    self.decimals = decimals_

@external
def mint(to: address, amount: uint256):
    self.balances[to] += amount

@external
@view
def balanceOf(account: address) -> uint256:
    return self.balances[account]
```

**Deployer** (`tests/mocks/deployers.py`):

```python
import boa

MOCK_ERC20 = boa.load_partial("tests/mocks/MockERC20.vy")
```

**Fixture** (`tests/conftest.py`):

```python
import pytest
from tests.mocks.deployers import MOCK_ERC20


@pytest.fixture(scope="module")
def mock_token():
    return MOCK_ERC20.deploy(18)


@pytest.fixture
def funded_account(mock_token):
    account = boa.env.generate_address("funded")
    mock_token.mint(account, 1000 * 10**18)
    return account
```

**Test using mock**:

```python
def test_deposit_with_mock_token(vault, mock_token, funded_account):
    amount = 100 * 10**18
    mock_token.approve(vault.address, amount, sender=funded_account)

    vault.deposit(amount, sender=funded_account)

    assert vault.balanceOf(funded_account) == amount
```

**Named-contract variant** — wire mock deploy in `moccasin.toml`:

```toml
[networks.pyevm.contracts.mock_token]
deployer_script = "script/mocks/deploy_mock_token.py"
```

```python
# script/mocks/deploy_mock_token.py
from tests.mocks.deployers import MOCK_ERC20
from moccasin.boa_tools import VyperContract

def moccasin_main() -> VyperContract:
    return MOCK_ERC20.deploy(18)
```

```python
# In test
from moccasin.config import get_config

network = get_config().get_active_network()
mock_token = network.manifest_named("mock_token")
```
