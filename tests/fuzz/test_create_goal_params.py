"""Hypothesis tests for create_goal duration and penalty caps."""

import boa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.utils import create_goal, now
from tests.utils.constants import (
    DEFAULT_START_PENALTY_BPS,
    DEFAULT_TARGET,
    MAX_DURATION,
    MAX_START_PENALTY_BPS,
    MIN_DURATION,
    MIN_TARGET,
)

SETTINGS = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@given(
    duration=st.integers(min_value=MIN_DURATION, max_value=MAX_DURATION),
    penalty=st.integers(min_value=0, max_value=MAX_START_PENALTY_BPS),
    target=st.integers(min_value=MIN_TARGET, max_value=MIN_TARGET * 100),
)
@SETTINGS
def test_create_goal_valid_params_succeeds(
    factory, asset, saver, duration, penalty, target
):
    with boa.env.anchor():
        goal, token_id = create_goal(
            factory,
            asset,
            saver,
            target=target,
            duration=duration,
            penalty=penalty,
        )
        assert factory.is_goal(goal.address)
        assert factory.ownerOf(token_id) == saver
        assert goal.TARGET() == target
        assert goal.START_PENALTY_BPS() == penalty
        assert goal.END_TIME() - goal.START_TIME() == duration


@given(duration=st.integers(min_value=1, max_value=MIN_DURATION - 1))
@SETTINGS
def test_create_goal_duration_too_short_reverts(factory, asset, saver, duration):
    end_time = now() + duration
    with boa.env.prank(saver), boa.reverts(dev="payday_factory: duration too short"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            end_time,
            DEFAULT_START_PENALTY_BPS,
        )


@given(
    extra=st.integers(min_value=1, max_value=MIN_DURATION),
)
@SETTINGS
def test_create_goal_duration_too_long_reverts(factory, asset, saver, extra):
    end_time = now() + MAX_DURATION + extra
    with boa.env.prank(saver), boa.reverts(dev="payday_factory: duration too long"):
        factory.create_goal(
            asset.address,
            DEFAULT_TARGET,
            end_time,
            DEFAULT_START_PENALTY_BPS,
        )


@given(penalty=st.integers(min_value=MAX_START_PENALTY_BPS + 1, max_value=10_000))
@SETTINGS
def test_create_goal_penalty_too_high_reverts(factory, asset, saver, penalty):
    end_time = now() + MIN_DURATION
    with boa.env.prank(saver), boa.reverts(dev="payday_factory: penalty too high"):
        factory.create_goal(asset.address, DEFAULT_TARGET, end_time, penalty)
