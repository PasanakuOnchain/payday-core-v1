"""Shared test helpers."""

import boa
from moccasin.boa_tools import VyperContract

from src import payday_goal
from tests.utils.constants import (
    DEFAULT_TARGET,
    MIN_DURATION,
)


def now() -> int:
    """Current titanoboa timestamp."""
    return boa.env.evm.patch.timestamp


def filter_logs(contract: VyperContract, event_name: str) -> list:
    """Return logs emitted by `contract` whose event class name matches."""
    return [log for log in contract.get_logs() if type(log).__name__ == event_name]


def create_goal(
    factory: VyperContract,
    asset: VyperContract,
    saver: str,
    target: int = DEFAULT_TARGET,
    duration: int = MIN_DURATION,
) -> tuple[VyperContract, int]:
    """Create a goal as `saver` and bind a `payday_goal` handle."""
    end_time = now() + duration
    with boa.env.prank(saver):
        addr, token_id = factory.create_goal(asset.address, target, end_time)
    return payday_goal.at(addr), int(token_id)


def fund_and_approve(
    token: VyperContract,
    owner: str,
    spender: str,
    amount: int,
) -> None:
    """Mint `amount` to `owner` and approve `spender`."""
    token.mint(owner, amount)
    token.approve(spender, amount, sender=owner)
