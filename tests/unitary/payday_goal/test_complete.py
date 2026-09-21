"""T5, T6, T12 — complete."""

import boa

from tests.utils import create_goal, filter_logs, fund_and_approve
from tests.utils.constants import MIN_DEPOSIT, URI_COMPLETED


def test_complete_when_principal_meets_target(factory, asset, saver):
    """T5: complete when principal >= target; URI → Completed."""
    goal, token_id = create_goal(factory, asset, saver)
    target = goal.TARGET()
    fund_and_approve(asset, saver, goal.address, target)
    goal.deposit(target, sender=saver)

    saver_before = asset.balanceOf(saver)
    goal.complete(sender=saver)
    logs = filter_logs(goal, "Completed")

    assert goal.closed() is True
    assert goal.principal() == 0
    assert asset.balanceOf(saver) == saver_before + target
    assert asset.balanceOf(goal.address) == 0
    assert factory.tokenURI(token_id) == URI_COMPLETED
    assert len(logs) == 1
    assert logs[0].owner == saver
    assert logs[0].amount == target


def test_complete_reverts_when_under_target(factory, asset, saver):
    """T6: complete reverts when under target."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)
    assert goal.principal() < goal.TARGET()

    with boa.env.prank(saver), boa.reverts(dev="payday_goal: under target"):
        goal.complete()


def test_complete_reverts_when_closed(factory, asset, saver):
    """T12: closed goal rejects complete."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, goal.TARGET())
    goal.deposit(goal.TARGET(), sender=saver)
    goal.complete(sender=saver)

    with boa.env.prank(saver), boa.reverts(dev="payday_goal: closed"):
        goal.complete()


def test_non_owner_cannot_complete(factory, asset, saver, other):
    """T3: non-owner cannot complete."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, goal.TARGET())
    goal.deposit(goal.TARGET(), sender=saver)

    with boa.env.prank(other), boa.reverts(dev="payday_goal: caller is not nft owner"):
        goal.complete()
