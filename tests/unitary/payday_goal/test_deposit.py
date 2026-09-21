"""T2, T3, T12 — deposits."""

import boa

from tests.utils import create_goal, filter_logs, fund_and_approve
from tests.utils.constants import MIN_DEPOSIT, URI_IN_PROGRESS


def test_deposit_as_nft_owner_increases_principal(factory, asset, saver):
    """T2: deposit as NFT owner increases principal; URI → InProgress."""
    goal, token_id = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)

    goal.deposit(MIN_DEPOSIT, sender=saver)
    logs = filter_logs(goal, "Deposit")

    assert goal.principal() == MIN_DEPOSIT
    assert asset.balanceOf(goal.address) == MIN_DEPOSIT
    assert factory.tokenURI(token_id) == URI_IN_PROGRESS
    assert len(logs) == 1
    assert logs[0].owner == saver
    assert logs[0].amount == MIN_DEPOSIT
    assert logs[0].principal == MIN_DEPOSIT


def test_second_deposit_keeps_in_progress_uri(factory, asset, saver):
    goal, token_id = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT * 2)
    goal.deposit(MIN_DEPOSIT, sender=saver)
    goal.deposit(MIN_DEPOSIT, sender=saver)
    assert goal.principal() == MIN_DEPOSIT * 2
    assert factory.tokenURI(token_id) == URI_IN_PROGRESS


def test_non_owner_cannot_deposit(factory, asset, saver, other):
    """T3: non-owner cannot deposit."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, other, goal.address, MIN_DEPOSIT)
    with boa.env.prank(other), boa.reverts(dev="payday_goal: caller is not nft owner"):
        goal.deposit(MIN_DEPOSIT)


def test_deposit_below_min_reverts(factory, asset, saver):
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    with boa.env.prank(saver), boa.reverts(dev="payday_goal: amount below min"):
        goal.deposit(MIN_DEPOSIT - 1)


def test_closed_goal_rejects_deposit(factory, asset, saver):
    """T12: closed goal rejects further deposit."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, goal.TARGET())
    goal.deposit(goal.TARGET(), sender=saver)
    goal.complete(sender=saver)

    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    with boa.env.prank(saver), boa.reverts(dev="payday_goal: closed"):
        goal.deposit(MIN_DEPOSIT)
