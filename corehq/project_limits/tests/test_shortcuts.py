import testil

from corehq.project_limits.rate_limiter import RateDefinition
from corehq.project_limits.shortcuts import get_standard_ratio_rate_definition


def test_get_standard_ratio_rate_definition():
    testil.eq(
        get_standard_ratio_rate_definition(events_per_day=23),
        RateDefinition(
            per_week=115,
            per_day=23,
            per_hour=3,
            per_minute=0.07,
            per_second=0.005,
        ),
    )
