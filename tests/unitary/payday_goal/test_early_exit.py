"""T7–T9, T12 — early exit and penalty math."""

import boa

from tests.utils import create_goal, filter_logs, fund_and_approve, now
from tests.utils.constants import (
    BPS_DENOMINATOR,
    DEFAULT_TARGET,
    MIN_DEPOSIT,
    MIN_DURATION,
    START_PENALTY_BPS,
    URI_COMPLETED,
)


def test_early_exit_mid_curve_fee_math(factory, asset, saver, treasury):
    """T7: early exit mid-curve — fee math + treasury ↑; URI → Completed."""
    goal, token_id = create_goal(factory, asset, saver)
    principal = MIN_DEPOSIT * 5
    fund_and_approve(asset, saver, goal.address, principal)
    goal.deposit(principal, sender=saver)
    assert goal.principal() < goal.TARGET()

    boa.env.time_travel(seconds=MIN_DURATION // 2)

    expected_bps = goal.penalty_bps()
    remaining = goal.END_TIME() - now()
    duration = goal.END_TIME() - goal.START_TIME()
    assert expected_bps == START_PENALTY_BPS * remaining // duration

    expected_fee = principal * expected_bps // BPS_DENOMINATOR
    expected_net = principal - expected_fee
    fee, net = goal.preview_early_exit()
    assert fee == expected_fee
    assert net == expected_net

    treasury_before = asset.balanceOf(treasury)
    saver_before = asset.balanceOf(saver)
    goal.early_exit(sender=saver)
    logs = filter_logs(goal, "EarlyExit")

    assert goal.closed() is True
    assert goal.principal() == 0
    assert asset.balanceOf(treasury) == treasury_before + expected_fee
    assert asset.balanceOf(saver) == saver_before + expected_net
    assert factory.tokenURI(token_id) == URI_COMPLETED
    assert len(logs) == 1
    assert logs[0].owner == saver
    assert logs[0].fee == expected_fee
    assert logs[0].net == expected_net
    assert logs[0].penalty_bps == expected_bps


def test_early_exit_at_end_time_fee_zero(factory, asset, saver, treasury):
    """T8: early exit at/after end_time — fee 0."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    boa.env.time_travel(seconds=MIN_DURATION)
    assert now() >= goal.END_TIME()
    assert goal.penalty_bps() == 0

    fee, net = goal.preview_early_exit()
    assert fee == 0
    assert net == MIN_DEPOSIT

    treasury_before = asset.balanceOf(treasury)
    saver_before = asset.balanceOf(saver)
    goal.early_exit(sender=saver)

    assert asset.balanceOf(treasury) == treasury_before
    assert asset.balanceOf(saver) == saver_before + MIN_DEPOSIT


def test_early_exit_reverts_when_at_or_above_target(factory, asset, saver):
    """T9: early exit reverts when principal >= target."""
    goal, _ = create_goal(factory, asset, saver, target=DEFAULT_TARGET)
    fund_and_approve(asset, saver, goal.address, DEFAULT_TARGET)
    goal.deposit(DEFAULT_TARGET, sender=saver)

    with boa.env.prank(saver), boa.reverts(dev="payday_goal: use complete"):
        goal.early_exit()


def test_early_exit_reverts_when_closed(factory, asset, saver):
    """T12: closed goal rejects early exit."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)
    goal.early_exit(sender=saver)

    with boa.env.prank(saver), boa.reverts(dev="payday_goal: closed"):
        goal.early_exit()


def test_non_owner_cannot_early_exit(factory, asset, saver, other):
    """T3: non-owner cannot early-exit."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    with boa.env.prank(other), boa.reverts(dev="payday_goal: caller is not nft owner"):
        goal.early_exit()


def test_penalty_at_start_is_full(factory, asset, saver):
    goal, _ = create_goal(factory, asset, saver)
    assert goal.penalty_bps() == START_PENALTY_BPS


def test_early_exit_dust_rounds_fee_down(factory, asset, saver, treasury):
    """Fee rounds down (favour saver). fee + net == principal."""
    goal, _ = create_goal(factory, asset, saver)
    fund_and_approve(asset, saver, goal.address, MIN_DEPOSIT)
    goal.deposit(MIN_DEPOSIT, sender=saver)

    fee, net = goal.preview_early_exit()
    assert fee + net == MIN_DEPOSIT
    assert fee == MIN_DEPOSIT * START_PENALTY_BPS // BPS_DENOMINATOR

    treasury_before = asset.balanceOf(treasury)
    goal.early_exit(sender=saver)
    assert asset.balanceOf(treasury) == treasury_before + fee
