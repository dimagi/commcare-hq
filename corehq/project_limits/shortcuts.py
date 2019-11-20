from corehq.project_limits.rate_limiter import RateDefinition

STANDARD_RATIO = RateDefinition(
    per_week=115,
    per_day=23,
    per_hour=3,
    per_minute=0.07,
    per_second=0.005,
).times(1 / 23)


def get_standard_ratio_rate_definition(events_per_day):
    return STANDARD_RATIO.times(events_per_day)
