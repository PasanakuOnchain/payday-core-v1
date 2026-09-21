"""Hypothesis property tests for the linear penalty curve."""

import boa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.utils import create_goal, now
from tests.utils.constants import DEFAULT_START_PENALTY_BPS, MIN_DURATION


@given(elapsed=st.integers(min_value=0, max_value=MIN_DURATION))
@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_penalty_matches_linear_formula(factory, asset, saver, elapsed):
    goal, _ = create_goal(factory, asset, saver, duration=MIN_DURATION)
    start = goal.START_TIME()
    end = goal.END_TIME()
    duration = end - start
    boa.env.time_travel(seconds=elapsed)

    current = now()
    if current <= start:
        expected = DEFAULT_START_PENALTY_BPS
    elif current >= end:
        expected = 0
    else:
        expected = DEFAULT_START_PENALTY_BPS * (end - current) // duration

    assert goal.penalty_bps() == expected
