"""T13 — URI state machine; T14–T16 soulbind."""

import boa

from tests.utils import create_goal, filter_logs, fund_and_approve
from tests.utils.constants import (
    MIN_DEPOSIT,
    URI_COMPLETED,
    URI_CREATED,
    URI_IN_PROGRESS,
)


def test_uri_created_in_progress_completed(factory, asset, saver):
    """T13 / T2 / T5: Created → InProgress → Completed."""
    goal, token_id = create_goal(factory, asset, saver)
    assert factory.tokenURI(token_id) == URI_CREATED

    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)
    assert factory.tokenURI(token_id) == URI_IN_PROGRESS

    remaining = goal.TARGET() - goal.principal()
    fund_and_approve(asset, saver, goal.address, remaining)
    goal.deposit(remaining, sender=saver)
    goal.complete(sender=saver)
    assert factory.tokenURI(token_id) == URI_COMPLETED


def test_non_goal_cannot_set_uri(factory, asset, saver, other):
    _, token_id = create_goal(factory, asset, saver)
    with boa.env.prank(other):
        with boa.reverts("payday_factory: caller is not goal"):
            factory.set_goal_uri_in_progress(token_id)
        with boa.reverts("payday_factory: caller is not goal"):
            factory.set_goal_uri_completed(token_id)


def test_owner_disable_transfers_blocks_transfer_deposit_still_works(
    factory, asset, saver, other
):
    """T14: owner disable_transfers → transfer reverts; deposit still works."""
    goal, token_id = create_goal(factory, asset, saver)

    factory.disable_transfers(token_id, sender=saver)
    logs = filter_logs(factory, "TransfersDisabled")
    assert factory.transfers_disabled(token_id) is True
    assert len(logs) == 1
    assert logs[0].token_id == token_id
    assert logs[0].owner == saver

    with boa.env.prank(saver), boa.reverts("payday_factory: transfers disabled"):
        factory.transferFrom(saver, other, token_id)

    with boa.env.prank(saver), boa.reverts("payday_factory: transfers disabled"):
        factory.safeTransferFrom(saver, other, token_id)

    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)
    assert goal.principal() == MIN_DEPOSIT
    assert factory.ownerOf(token_id) == saver


def test_disable_transfers_cannot_be_undone(factory, asset, saver):
    """T15: disable_transfers cannot be undone; second call reverts."""
    _, token_id = create_goal(factory, asset, saver)
    factory.disable_transfers(token_id, sender=saver)

    with boa.reverts("payday_factory: transfers already disabled"):
        factory.disable_transfers(token_id, sender=saver)

    assert factory.transfers_disabled(token_id) is True


def test_non_owner_cannot_soulbind(factory, asset, saver, other):
    """T16: non-owner cannot soulbind."""
    _, token_id = create_goal(factory, asset, saver)
    with boa.reverts("payday_factory: caller is not token owner"):
        factory.disable_transfers(token_id, sender=other)
    assert factory.transfers_disabled(token_id) is False


def test_soulbind_clears_approval(factory, asset, saver, other):
    _, token_id = create_goal(factory, asset, saver)
    factory.approve(other, token_id, sender=saver)
    assert factory.getApproved(token_id) == other

    factory.disable_transfers(token_id, sender=saver)
    assert factory.getApproved(token_id) == "0x0000000000000000000000000000000000000000"

    with boa.env.prank(other), boa.reverts("payday_factory: transfers disabled"):
        factory.transferFrom(saver, other, token_id)
