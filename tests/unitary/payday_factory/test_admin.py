"""Owner-only factory admin: treasury, two-step ownership, and asset allowlist."""

import boa

from tests.utils import filter_logs, now
from tests.utils.constants import (
    DEFAULT_TARGET,
    MIN_DEPOSIT,
    MIN_DURATION,
    MIN_TARGET,
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


def test_transfer_ownership_by_non_owner_reverts(factory, other):
    with boa.env.prank(other), boa.reverts("ownable: caller is not the owner"):
        factory.transfer_ownership(other)


def test_transfer_ownership_waits_for_accept(factory, owner, other):
    factory.transfer_ownership(other, sender=owner)
    assert factory.owner() == owner
    assert factory.pending_owner() == other

    factory.accept_ownership(sender=other)
    assert factory.owner() == other
    assert factory.pending_owner() == EMPTY


def test_accept_ownership_by_stranger_reverts(factory, owner, other, saver):
    factory.transfer_ownership(other, sender=owner)
    with (
        boa.env.prank(saver),
        boa.reverts("ownable_2step: caller is not the new owner"),
    ):
        factory.accept_ownership()
    assert factory.owner() == owner


def test_transfer_ownership_to_zero_clears_pending(factory, owner, other):
    factory.transfer_ownership(other, sender=owner)
    factory.transfer_ownership(EMPTY, sender=owner)
    assert factory.pending_owner() == EMPTY
    assert factory.owner() == owner

    with (
        boa.env.prank(other),
        boa.reverts("ownable_2step: caller is not the new owner"),
    ):
        factory.accept_ownership()


def test_set_asset_allowed_zero_asset_reverts(factory, owner):
    with boa.env.prank(owner), boa.reverts(dev="payday_factory: zero asset"):
        factory.set_asset_allowed(EMPTY, True, MIN_TARGET, MIN_DEPOSIT)


def test_set_asset_allowed_zero_min_deposit_reverts(factory, owner, asset):
    with (
        boa.env.prank(owner),
        boa.reverts(dev="payday_factory: zero min deposit # nosplit"),
    ):
        factory.set_asset_allowed(asset.address, True, MIN_TARGET, 0)


def test_set_asset_allowed_min_target_below_min_deposit_reverts(factory, owner, asset):
    with (
        boa.env.prank(owner),
        boa.reverts(dev="payday_factory: min target below min deposit # nosplit"),
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
            sender=saver,
        )
