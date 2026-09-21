"""Goal constructor argument validation via direct CREATE (test-only)."""

import boa
from src import payday_goal

from tests.utils import now
from tests.utils.constants import (
    DEFAULT_START_PENALTY_BPS,
    DEFAULT_TARGET,
    MIN_DEPOSIT,
    MIN_DURATION,
)

EMPTY = "0x0000000000000000000000000000000000000000"


def _deploy(
    factory_addr: str,
    asset_addr: str,
    treasury_addr: str,
    *,
    target: int = DEFAULT_TARGET,
    start_time: int | None = None,
    end_time: int | None = None,
    min_deposit: int = MIN_DEPOSIT,
):
    start = now() if start_time is None else start_time
    end = start + MIN_DURATION if end_time is None else end_time
    return payday_goal.deploy(
        factory_addr,
        asset_addr,
        treasury_addr,
        EMPTY,
        target,
        start,
        end,
        DEFAULT_START_PENALTY_BPS,
        0,
        min_deposit,
    )


def test_constructor_zero_factory_reverts(factory, asset, treasury):
    with boa.reverts(dev="payday_goal: zero factory"):
        _deploy(EMPTY, asset.address, treasury)


def test_constructor_zero_asset_reverts(factory, treasury):
    with boa.reverts(dev="payday_goal: zero asset"):
        _deploy(factory.address, EMPTY, treasury)


def test_constructor_zero_treasury_reverts(factory, asset):
    with boa.reverts(dev="payday_goal: zero treasury"):
        _deploy(factory.address, asset.address, EMPTY)


def test_constructor_zero_target_reverts(factory, asset, treasury):
    with boa.reverts(dev="payday_goal: zero target"):
        _deploy(factory.address, asset.address, treasury, target=0)


def test_constructor_zero_min_deposit_reverts(factory, asset, treasury):
    with boa.reverts(dev="payday_goal: zero min deposit"):
        _deploy(factory.address, asset.address, treasury, min_deposit=0)


def test_constructor_end_time_not_after_start_reverts(factory, asset, treasury):
    start = now()
    with boa.reverts(dev="payday_goal: bad times"):
        _deploy(
            factory.address,
            asset.address,
            treasury,
            start_time=start,
            end_time=start,
        )
