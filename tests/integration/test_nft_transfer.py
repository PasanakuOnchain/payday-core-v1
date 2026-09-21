"""T4 — NFT transfer moves goal control."""

import boa

from tests.utils import create_goal, fund_and_approve
from tests.utils.constants import MIN_DEPOSIT


def test_new_owner_can_deposit_old_cannot(factory, asset, saver, other):
    """T4: after NFT transfer, new owner can deposit; old cannot."""
    goal, token_id = create_goal(factory, asset, saver)

    factory.transferFrom(saver, other, token_id, sender=saver)
    assert factory.ownerOf(token_id) == other
    assert factory.owner_of_goal(goal.address) == other

    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    with boa.env.prank(saver), boa.reverts("payday_goal: caller is not nft owner"):
        goal.deposit(MIN_DEPOSIT)

    fund_and_approve(asset, other, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=other)
    assert goal.principal() == MIN_DEPOSIT


def test_new_owner_can_complete(factory, asset, saver, other):
    goal, token_id = create_goal(factory, asset, saver)
    factory.safeTransferFrom(saver, other, token_id, sender=saver)

    target = goal.TARGET()
    fund_and_approve(asset, other, goal.address, target)
    goal.deposit(target, sender=other)
    goal.complete(sender=other)
    assert goal.closed() is True
    assert asset.balanceOf(other) == target
