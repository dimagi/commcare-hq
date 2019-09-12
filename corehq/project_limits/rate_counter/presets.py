from datetime import timedelta

from corehq.project_limits.rate_counter.rate_counter import \
    SlidingWindowRateCounter

week_rate_counter = SlidingWindowRateCounter(
    'week',
    timedelta(days=7).total_seconds(),
    grains_per_window=7,
    memoize_timeout=timedelta(hours=6).total_seconds()
)

day_rate_counter = SlidingWindowRateCounter(
    'day',
    timedelta(days=1).total_seconds(),
    grains_per_window=4,
    memoize_timeout=timedelta(hours=6).total_seconds()
)

hour_rate_counter = SlidingWindowRateCounter(
    'hour',
    timedelta(hours=1).total_seconds(),
    grains_per_window=3,
    memoize_timeout=timedelta(hours=1).total_seconds()
)

minute_rate_counter = SlidingWindowRateCounter(
    'minute',
    timedelta(minutes=1).total_seconds(),
    grains_per_window=2,
    memoize_timeout=timedelta(minutes=1).total_seconds()
)

second_rate_counter = SlidingWindowRateCounter(
    'second',
    timedelta(seconds=1).total_seconds(),
    grains_per_window=1,
    memoize_timeout=timedelta(seconds=1).total_seconds()
)
