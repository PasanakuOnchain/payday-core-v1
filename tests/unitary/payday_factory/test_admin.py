"""Owner-only factory admin: treasury, URIs, and asset allowlist."""

import boa

from tests.utils import create_goal, filter_logs, now
from tests.utils.constants import (
    DEFAULT_START_PENALTY_BPS,
    DEFAULT_TARGET,
    MIN_DEPOSIT,
    MIN_DURATION,
    MIN_TARGET,
    URI_COMPLETED,
    URI_CREATED,
    URI_IN_PROGRESS,
)

EMPTY = "0x0000000000000000000000000000000000000000"


def test_set_treasury_by_owner_succeeds(factory, owner):
    new_treasury = boa.env.generate_address("new_treasury")
    factory.set_treasury(new_treasury, sender=owner)
    logs = filter_logs(factory, "TreasuryUpdated")

    assert factory.treasury() == new_treasury
    assert len(logs) == 1
    assert logs[0].treasury == new_treasury


def test_set_treasury_by_non_owner_reverts(factory, other):
    new_treasury = boa.env.generate_address("new_treasury")
    with boa.env.prank(other), boa.reverts("ownable: caller is not the owner"):
        factory.set_treasury(new_treasury)


def test_set_treasury_zero_address_reverts(factory, owner):
    with boa.env.prank(owner), boa.reverts(dev="payday_factory: zero treasury"):
        factory.set_treasury(EMPTY)


def test_set_uris_by_owner_succeeds(factory, owner):
    created = "ipfs://payday/v2/created.json"
    in_progress = "ipfs://payday/v2/in-progress.json"
    completed = "ipfs://payday/v2/completed.json"

    factory.set_uris(created, in_progress, completed, sender=owner)
    logs = filter_logs(factory, "UrisUpdated")

    assert factory.uri_created() == created
    assert factory.uri_in_progress() == in_progress
    assert factory.uri_completed() == completed
    assert len(logs) == 1
    assert logs[0].uri_created == created
    assert logs[0].uri_in_progress == in_progress
    assert logs[0].uri_completed == completed


def test_set_uris_empty_created_reverts(factory, owner):
    with boa.env.prank(owner), boa.reverts(dev="payday_factory: empty created uri"):
        factory.set_uris("", URI_IN_PROGRESS, URI_COMPLETED)


def test_set_uris_empty_progress_reverts(factory, owner):
    with boa.env.prank(owner), boa.reverts(dev="payday_factory: empty progress uri"):
        factory.set_uris(URI_CREATED, "", URI_COMPLETED)


def test_set_uris_empty_completed_reverts(factory, owner):
    with boa.env.prank(owner), boa.reverts(dev="payday_factory: empty completed uri"):
        factory.set_uris(URI_CREATED, URI_IN_PROGRESS, "")


def test_set_uris_by_non_owner_reverts(factory, other):
    with boa.env.prank(other), boa.reverts("ownable: caller is not the owner"):
        factory.set_uris(URI_CREATED, URI_IN_PROGRESS, URI_COMPLETED)


def test_set_asset_allowed_zero_asset_reverts(factory, owner):
    with boa.env.prank(owner), boa.reverts(dev="payday_factory: zero asset"):
        factory.set_asset_allowed(EMPTY, True, MIN_TARGET, MIN_DEPOSIT)


def test_set_asset_allowed_zero_min_deposit_reverts(factory, owner, asset):
    with boa.env.prank(owner), boa.reverts(dev="payday_factory: zero min deposit"):
        factory.set_asset_allowed(asset.address, True, MIN_TARGET, 0)


def test_set_asset_allowed_min_target_below_min_deposit_reverts(factory, owner, asset):
    with boa.env.prank(owner), boa.reverts(
        dev="payday_factory: min target below min deposit"
    ):
        factory.set_asset_allowed(asset.address, True, MIN_DEPOSIT - 1, MIN_DEPOSIT)


def test_set_asset_allowed_revoke_then_create_goal_reverts(
    factory, owner, asset, saver
):
    factory.set_asset_allowed(asset.address, False, 0, 0, sender=owner)
    logs = filter_logs(factory, "AssetAllowlistUpdated")
    assert len(logs) == 1
    assert logs[0].asset == asset.address
    assert logs[0].allowed is False

    end_time = now() + MIN_DURATION
    with boa.reverts(dev="payday_factory: asset not allowed"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            end_time,
            DEFAULT_START_PENALTY_BPS,
            sender=saver,
        )


def test_set_uris_apply_to_next_lifecycle_transition(factory, owner, asset, saver):
    """Existing tokens keep Created URI; later transitions use the new packs."""
    goal, token_id = create_goal(factory, asset, saver)
    assert factory.tokenURI(token_id) == URI_CREATED

    created = "ipfs://payday/v2/created.json"
    in_progress = "ipfs://payday/v2/in-progress.json"
    completed = "ipfs://payday/v2/completed.json"
    factory.set_uris(created, in_progress, completed, sender=owner)

    assert factory.tokenURI(token_id) == URI_CREATED
    new_goal, new_id = create_goal(factory, asset, saver)
    assert factory.tokenURI(new_id) == created
    assert new_goal.address != goal.address
