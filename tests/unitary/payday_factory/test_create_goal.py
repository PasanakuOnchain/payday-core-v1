"""T1, T10, T11 — factory create_goal, allowlist, duration/penalty caps."""

import boa

from tests.utils import create_goal, filter_logs, now
from tests.utils.constants import (
    DEFAULT_START_PENALTY_BPS,
    DEFAULT_TARGET,
    MAX_DURATION,
    MAX_START_PENALTY_BPS,
    MIN_DEPOSIT,
    MIN_DURATION,
    MIN_TARGET,
    NAME,
    SYMBOL,
    URI_CREATED,
)


def test_create_goal_deploys_blueprint_and_mints_nft(factory, asset, saver):
    """T1: create_goal deploys via blueprint + mints NFT to creator."""
    assert factory.name() == NAME
    assert factory.symbol() == SYMBOL
    assert factory.totalSupply() == 0

    goal, token_id = create_goal(factory, asset, saver)
    created_logs = filter_logs(factory, "GoalCreated")

    assert token_id == 0
    assert factory.totalSupply() == 1
    assert factory.ownerOf(token_id) == saver
    assert factory.balanceOf(saver) == 1
    assert factory.goals(token_id) == goal.address
    assert factory.token_of(goal.address) == token_id
    assert factory.is_goal(goal.address)
    assert factory.owner_of_goal(goal.address) == saver
    assert goal.address.lower() != factory.GOAL_BLUEPRINT().lower()

    assert goal.FACTORY() == factory.address
    assert goal.ASSET() == asset.address
    assert goal.TARGET() == DEFAULT_TARGET
    assert goal.START_PENALTY_BPS() == DEFAULT_START_PENALTY_BPS
    assert goal.TOKEN_ID() == token_id
    assert goal.MIN_DEPOSIT() == MIN_DEPOSIT
    assert goal.principal() == 0
    assert goal.closed() is False
    assert goal.VAULT() == "0x0000000000000000000000000000000000000000"

    assert len(created_logs) == 1
    assert created_logs[0].goal == goal.address
    assert created_logs[0].token_id == token_id
    assert created_logs[0].creator == saver
    assert created_logs[0].asset == asset.address


def test_token_uri_is_created_pack_at_mint(factory, asset, saver):
    """T13: tokenURI is Created at mint; not snekmate default (base + id)."""
    goal, token_id = create_goal(factory, asset, saver)

    uri = factory.tokenURI(token_id)
    assert uri == URI_CREATED
    assert uri != ""
    assert not uri.endswith(str(token_id))
    assert goal.address != "0x0000000000000000000000000000000000000000"


def test_non_allowlisted_asset_cannot_create(owner, treasury, asset, saver):
    """T10: non-allowlisted asset cannot create."""
    from script.deploy import deploy

    with boa.env.prank(owner):
        _, factory = deploy(treasury)

    end_time = now() + MIN_DURATION
    with boa.reverts(dev="payday_factory: asset not allowed"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            end_time,
            DEFAULT_START_PENALTY_BPS,
            sender=saver,
        )


def test_duration_below_min_reverts(factory, asset, saver):
    """T11: duration cap — too short."""
    end_time = now() + MIN_DURATION - 1
    with boa.reverts(dev="payday_factory: duration too short"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            end_time,
            DEFAULT_START_PENALTY_BPS,
            sender=saver,
        )


def test_duration_above_max_reverts(factory, asset, saver):
    """T11: duration cap — too long."""
    end_time = now() + MAX_DURATION + 1
    with boa.reverts(dev="payday_factory: duration too long"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            end_time,
            DEFAULT_START_PENALTY_BPS,
            sender=saver,
        )


def test_end_time_not_future_reverts(factory, asset, saver):
    """T11: end_time must be in the future."""
    with boa.reverts(dev="payday_factory: end time not future"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            now(),
            DEFAULT_START_PENALTY_BPS,
            sender=saver,
        )


def test_penalty_above_max_reverts(factory, asset, saver):
    """T11: penalty cap enforced."""
    end_time = now() + MIN_DURATION
    with boa.env.prank(saver), boa.reverts(dev="payday_factory: penalty too high"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            end_time,
            MAX_START_PENALTY_BPS + 1,
        )


def test_target_below_min_reverts(factory, asset, saver):
    """T11: per-asset min target enforced."""
    end_time = now() + MIN_DURATION
    with boa.reverts(dev="payday_factory: target too low"):
        factory.create_goal(
            asset.address,
            MIN_TARGET - 1,
            end_time,
            DEFAULT_START_PENALTY_BPS,
            sender=saver,
        )


def test_max_penalty_and_duration_succeed(factory, asset, saver):
    """T11: boundaries of duration and penalty caps succeed."""
    goal, _ = create_goal(
        factory,
        asset,
        saver,
        duration=MAX_DURATION,
        penalty=MAX_START_PENALTY_BPS,
    )
    assert goal.START_PENALTY_BPS() == MAX_START_PENALTY_BPS
    assert goal.END_TIME() - goal.START_TIME() == MAX_DURATION


def test_non_owner_cannot_allowlist(factory, other, asset):
    with boa.env.prank(other), boa.reverts("ownable: caller is not the owner"):
        factory.set_asset_allowed(asset.address, True, MIN_TARGET, MIN_DEPOSIT)
