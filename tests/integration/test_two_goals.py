"""Two savers, two NFTs — close paths stay independent."""

from tests.utils import create_goal, fund_and_approve
from tests.utils.constants import MIN_DEPOSIT, URI_COMPLETED, URI_IN_PROGRESS


def test_two_goals_complete_and_early_exit_independently(
    factory, asset, saver, other, treasury
):
    goal_a, token_a = create_goal(factory, asset, saver)
    goal_b, token_b = create_goal(factory, asset, other)

    target = goal_a.TARGET()
    fund_and_approve(asset, saver, goal_a.address, target)
    goal_a.deposit(target, sender=saver)

    fund_and_approve(asset, other, goal_b.address, MIN_DEPOSIT)
    goal_b.deposit(MIN_DEPOSIT, sender=other)

    assert factory.tokenURI(token_a) == URI_IN_PROGRESS
    assert factory.tokenURI(token_b) == URI_IN_PROGRESS
    assert factory.ownerOf(token_a) == saver
    assert factory.ownerOf(token_b) == other

    saver_before = asset.balanceOf(saver)
    goal_a.complete(sender=saver)
    assert goal_a.closed() is True
    assert goal_b.closed() is False
    assert asset.balanceOf(saver) == saver_before + target
    assert factory.tokenURI(token_a) == URI_COMPLETED
    assert factory.tokenURI(token_b) == URI_IN_PROGRESS

    fee, net = goal_b.preview_early_exit()
    other_before = asset.balanceOf(other)
    treasury_before = asset.balanceOf(treasury)
    goal_b.early_exit(sender=other)

    assert goal_b.closed() is True
    assert asset.balanceOf(other) == other_before + net
    assert asset.balanceOf(treasury) == treasury_before + fee
    assert factory.tokenURI(token_b) == URI_COMPLETED
    assert factory.ownerOf(token_a) == saver
    assert factory.ownerOf(token_b) == other
