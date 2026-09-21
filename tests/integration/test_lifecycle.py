"""End-to-end lifecycle covering create → save → free unlock."""

from tests.utils import create_goal, fund_and_approve
from tests.utils.constants import URI_COMPLETED, URI_CREATED, URI_IN_PROGRESS


def test_full_success_lifecycle(factory, asset, saver):
    goal, token_id = create_goal(factory, asset, saver)
    assert factory.tokenURI(token_id) == URI_CREATED

    target = goal.TARGET()
    fund_and_approve(asset, saver, goal.address, target)
    goal.deposit(target, sender=saver)
    assert factory.tokenURI(token_id) == URI_IN_PROGRESS

    goal.complete(sender=saver)
    assert factory.tokenURI(token_id) == URI_COMPLETED
    assert goal.closed() is True
    assert asset.balanceOf(saver) == target
