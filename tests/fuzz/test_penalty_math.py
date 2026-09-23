"""Hypothesis property tests for the linear penalty curve."""

import boa
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from tests.utils import create_goal, fund_and_approve, now
from tests.utils.constants import (
    BPS_DENOMINATOR,
    DAY,
    DEFAULT_TARGET,
    MAX_DURATION,
    MIN_DEPOSIT,
    MIN_DURATION,
    START_PENALTY_BPS,
)

SETTINGS = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@given(elapsed=st.integers(min_value=0, max_value=MIN_DURATION))
@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_penalty_matches_linear_formula(factory, asset, saver, elapsed):
    with boa.env.anchor():
        goal, _ = create_goal(factory, asset, saver, duration=MIN_DURATION)
        start = goal.START_TIME()
        end = goal.END_TIME()
        duration = end - start
        boa.env.time_travel(seconds=elapsed)

        current = now()
        if current <= start:
            expected = START_PENALTY_BPS
        elif current >= end:
            expected = 0
        else:
            expected = START_PENALTY_BPS * (end - current) // duration

        assert goal.penalty_bps() == expected


@given(
    elapsed=st.integers(min_value=0, max_value=MAX_DURATION + DAY),
    duration=st.integers(min_value=MIN_DURATION, max_value=MAX_DURATION),
)
@SETTINGS
def test_penalty_bps_stays_within_bounds(factory, asset, saver, elapsed, duration):
    with boa.env.anchor():
        goal, _ = create_goal(factory, asset, saver, duration=duration)
        boa.env.time_travel(seconds=elapsed)
        bps = goal.penalty_bps()
        assert 0 <= bps <= START_PENALTY_BPS
        assert bps <= goal.START_PENALTY_BPS()


@given(principal=st.integers(min_value=MIN_DEPOSIT, max_value=DEFAULT_TARGET - 1))
@SETTINGS
def test_preview_early_exit_fee_plus_net_equals_principal(
    factory, asset, saver, principal
):
    with boa.env.anchor():
        goal, _ = create_goal(factory, asset, saver)
        fund_and_approve(asset, saver, goal.address, principal)
        goal.deposit(principal, sender=saver)

        fee, net = goal.preview_early_exit()
        bps = goal.penalty_bps()
        assert fee + net == principal
        assert fee == principal * bps // BPS_DENOMINATOR


@given(
    t1=st.integers(min_value=0, max_value=MIN_DURATION),
    t2=st.integers(min_value=0, max_value=MIN_DURATION),
)
@SETTINGS
def test_penalty_non_increasing_as_time_advances(factory, asset, saver, t1, t2):
    assume(t2 >= t1)
    with boa.env.anchor():
        goal, _ = create_goal(factory, asset, saver, duration=MIN_DURATION)
        boa.env.time_travel(seconds=t1)
        first = goal.penalty_bps()
        boa.env.time_travel(seconds=t2 - t1)
        second = goal.penalty_bps()
        assert second <= first
