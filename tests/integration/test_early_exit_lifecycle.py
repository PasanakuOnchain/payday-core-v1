"""Create → save under target → mid-curve early exit → closed."""

import boa

from tests.utils import create_goal, fund_and_approve
from tests.utils.constants import (
    BPS_DENOMINATOR,
    MIN_DEPOSIT,
    MIN_DURATION,
    URI_COMPLETED,
    URI_CREATED,
    URI_IN_PROGRESS,
)


def test_early_exit_full_lifecycle(factory, asset, saver, treasury):
    goal, token_id = create_goal(factory, asset, saver)
    assert factory.tokenURI(token_id) == URI_CREATED

    principal = MIN_DEPOSIT * 5
    fund_and_approve(asset, saver, goal.address, principal)
    goal.deposit(principal, sender=saver)
    assert factory.tokenURI(token_id) == URI_IN_PROGRESS
    assert goal.principal() < goal.TARGET()

    boa.env.time_travel(seconds=MIN_DURATION // 2)
    fee, net = goal.preview_early_exit()
    assert fee + net == principal
    assert fee == principal * goal.penalty_bps() // BPS_DENOMINATOR

    treasury_before = asset.balanceOf(treasury)
    saver_before = asset.balanceOf(saver)
    goal.early_exit(sender=saver)

    assert factory.tokenURI(token_id) == URI_COMPLETED
    assert goal.closed() is True
    assert goal.principal() == 0
    assert asset.balanceOf(treasury) == treasury_before + fee
    assert asset.balanceOf(saver) == saver_before + net

    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    with boa.env.prank(saver), boa.reverts(dev="payday_goal: closed"):
        goal.deposit(MIN_DEPOSIT)
    with boa.env.prank(saver), boa.reverts(dev="payday_goal: closed"):
        goal.early_exit()
    with boa.env.prank(saver), boa.reverts(dev="payday_goal: closed"):
        goal.complete()
