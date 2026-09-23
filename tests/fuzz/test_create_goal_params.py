"""Hypothesis tests for create_goal duration caps and the fixed penalty."""

import boa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.utils import create_goal, now
from tests.utils.constants import (
    DEFAULT_TARGET,
    MAX_DURATION,
    MIN_DURATION,
    MIN_TARGET,
    START_PENALTY_BPS,
)

SETTINGS = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@given(
    duration=st.integers(min_value=MIN_DURATION, max_value=MAX_DURATION),
    target=st.integers(min_value=MIN_TARGET, max_value=MIN_TARGET * 100),
)
@SETTINGS
def test_create_goal_valid_params_succeeds(factory, asset, saver, duration, target):
    with boa.env.anchor():
        goal, token_id = create_goal(
            factory,
            asset,
            saver,
            target=target,
            duration=duration,
        )
        assert factory.is_goal(goal.address)
        assert factory.ownerOf(token_id) == saver
        assert goal.TARGET() == target
        assert goal.START_PENALTY_BPS() == START_PENALTY_BPS
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
        )
