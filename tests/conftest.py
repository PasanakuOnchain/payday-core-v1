import boa
import pytest
from moccasin.boa_tools import VyperContract

from script.deploy import deploy
from tests.mocks.deployers import MOCK_ERC20
from tests.utils.constants import MIN_DEPOSIT, MIN_TARGET

boa.env.enable_fast_mode()


@pytest.fixture(scope="session")
def owner() -> str:
    return boa.env.eoa


@pytest.fixture(scope="session")
def treasury() -> str:
    addr = boa.env.generate_address("treasury")
    boa.env.set_balance(addr, 10**18)
    return addr


@pytest.fixture(scope="session")
def saver() -> str:
    addr = boa.env.generate_address("saver")
    boa.env.set_balance(addr, 10**18)
    return addr


@pytest.fixture(scope="session")
def other() -> str:
    addr = boa.env.generate_address("other")
    boa.env.set_balance(addr, 10**18)
    return addr


@pytest.fixture
def asset() -> VyperContract:
    return MOCK_ERC20.deploy("USD Coin", "USDC", 6)


@pytest.fixture
def factory(owner: str, treasury: str, asset: VyperContract) -> VyperContract:
    with boa.env.prank(owner):
        _, deployed = deploy(treasury)
        deployed.set_asset_allowed(asset.address, True, MIN_TARGET, MIN_DEPOSIT)
    return deployed
