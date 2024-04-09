import functools
from datetime import timedelta
import testil

from corehq.project_limits.rate_counter.rate_counter import CounterCache, \
    FixedWindowRateCounter, SlidingWindowRateCounter


_CounterCache = CounterCache
_FixedWindowRateCounter = functools.partial(
    FixedWindowRateCounter,
    _CounterCache=_CounterCache
)
_SlidingWindowRateCounter = functools.partial(
    SlidingWindowRateCounter,
    _FixedWindowRateCounter=_FixedWindowRateCounter
)


DAYS = timedelta(days=1).total_seconds()


def test_fixed_window_rate_counter():
    # this timestamp is chosen to be 6 days into a week window
    timestamp = (1000 * 7 * DAYS + 6 * DAYS)
    counter = _FixedWindowRateCounter('test-week', 7 * DAYS)
    counter.counter.shared_cache.clear()

    testil.eq(counter.increment_and_get('alice', timestamp=timestamp), 1)
    testil.eq(counter.increment_and_get('alice', timestamp=timestamp), 2)
    testil.eq(counter.increment_and_get('alice', timestamp=timestamp), 3)

    testil.eq(counter.increment_and_get('bob', timestamp=timestamp), 1)

    testil.eq(counter.get('alice', timestamp=timestamp), 3)
    testil.eq(counter.get('alice', timestamp=timestamp - 6 * DAYS), 3)
    testil.eq(counter.get('alice', timestamp=timestamp - 7 * DAYS), 0)
    testil.eq(counter.get('alice', timestamp=timestamp + 1 * DAYS), 0)


def float_eq(f1, f2, text=None):
    f1 = round(f1, 6)
    f2 = round(f2, 6)
    testil.eq(f1, f2, text)


def test_sliding_window_with_grains_rate_counter():
    # this timestamp is chosen to be 6 days into a week window

    timestamp = (1000 * 7 * DAYS + 6 * DAYS)
    counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS)
    counter.grain_counter.counter.shared_cache.clear()

    testil.eq(counter.increment_and_get('alice', timestamp=timestamp), 1)
    testil.eq(counter.increment_and_get('alice', timestamp=timestamp), 2)
    testil.eq(counter.increment_and_get('alice', timestamp=timestamp), 3)

    testil.eq(counter.increment_and_get('bob', timestamp=timestamp), 1)

    testil.eq(counter.get('alice', timestamp=timestamp), 3)
    testil.eq(counter.get('alice', timestamp=timestamp - 6 * DAYS), 3)
    testil.eq(counter.get('alice', timestamp=timestamp - 7 * DAYS), 0)

    # As time moves forward beyond the period boundary
    # the value fades linearly to 0 by the end of the following period
    float_eq(counter.get('alice', timestamp=timestamp + 1 * DAYS), 3)
    float_eq(counter.get('alice', timestamp=timestamp + 2 * DAYS), 3 * 6. / 7)
    float_eq(counter.get('alice', timestamp=timestamp + 3 * DAYS), 3 * 5. / 7)
    float_eq(counter.get('alice', timestamp=timestamp + 4 * DAYS), 3 * 4. / 7)
    float_eq(counter.get('alice', timestamp=timestamp + 5 * DAYS), 3 * 3. / 7)
    float_eq(counter.get('alice', timestamp=timestamp + 6 * DAYS), 3 * 2. / 7)
    float_eq(counter.get('alice', timestamp=timestamp + 7 * DAYS), 3 * 1. / 7)
    float_eq(counter.get('alice', timestamp=timestamp + 8 * DAYS), 0)

    float_eq(counter.increment_and_get('alice', timestamp=timestamp + 1 * DAYS), 4)
    float_eq(counter.get('alice', timestamp=timestamp + 2 * DAYS), 3 * 6. / 7 + 1)


class TestSlidingWindowCountAndWait:

    def test_sliding_window_over_one_grain(self):
        timestamp = 1000 * 7 * DAYS
        scope = "alice"
        counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS, grains_per_window=1)
        counter.grain_counter.counter.shared_cache.clear()

        counter.increment(scope, timestamp=timestamp)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp)
        testil.eq(hits, 1)
        testil.eq(round(wait_time / DAYS), 7)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 6 * DAYS)
        testil.eq(hits, 1)
        # wait_time / DAYS = 0.9999999999999994
        testil.eq(round(wait_time / DAYS), 1)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 6.5 * DAYS)
        testil.eq(hits, 1)
        testil.eq(round(wait_time / DAYS, 2), 0.5)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 7 * DAYS)
        testil.eq(hits, 1)
        testil.eq(round(wait_time / DAYS, 2), 0.0)

    def test_sliding_window_multiple_grains(self):
        timestamp = 1000 * 7 * DAYS
        scope = 'bob'
        counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS, grains_per_window=7)
        counter.grain_counter.counter.shared_cache.clear()

        counter.increment(scope, timestamp=timestamp)

        for day_n in range(0, 7):
            hits, wait_time = counter.get_count_and_wait_time(
                scope, threshold=1, timestamp=timestamp + day_n * DAYS
            )
            testil.eq(hits, 1)
            testil.eq(wait_time / DAYS, 7 - day_n)

    def test_sliding_window_multiple_grains_basic(self):
        timestamp = 1000 * 7 * DAYS
        scope = 'elton'
        counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS, grains_per_window=7)
        counter.grain_counter.counter.shared_cache.clear()

        counter.increment(scope, timestamp=timestamp)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 7)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 0.5 * DAYS)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 6.5)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 1 * DAYS)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 6)

    def test_sliding_window_multiple_grains_more_complex(self):
        timestamp = 1000 * 7 * DAYS
        scope = 'john'
        counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS, grains_per_window=7)
        counter.grain_counter.counter.shared_cache.clear()

        counter.increment(scope, timestamp=timestamp)
        counter.increment(scope, timestamp=timestamp + 1 * DAYS)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 7)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 1 * DAYS)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 7)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 2 * DAYS)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 6)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 7 * DAYS)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 1)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 8 * DAYS)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 0)

    def test_sliding_window_multiple_grains_more_complex_2(self):
        timestamp = 1000 * 7 * DAYS
        scope = 'jack'
        counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS, grains_per_window=7)
        counter.grain_counter.counter.shared_cache.clear()

        counter.increment(scope, timestamp=timestamp - 1 * DAYS)
        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 6)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 6 * DAYS)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 0)

        # Test wait time for 2 hits
        counter.increment(scope, timestamp=timestamp - 1 * DAYS)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 6.5)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=2, timestamp=timestamp)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 6)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 6 * DAYS)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 0.5)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp + 6.5 * DAYS)
        testil.eq(hits, 1)
        testil.eq(wait_time / DAYS, 0.0)

        # Test wait time for 3 hits
        counter.increment(scope, timestamp=timestamp - 1 * DAYS)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=1, timestamp=timestamp)
        testil.eq(hits, 3)
        wait_time_days = wait_time / DAYS
        testil.eq(round(wait_time_days, 3), 6.667)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=2, timestamp=timestamp)
        testil.eq(hits, 3)
        wait_time_days = wait_time / DAYS
        testil.eq(round(wait_time_days, 2), 6.33)

        hits, wait_time = counter.get_count_and_wait_time(scope, threshold=3, timestamp=timestamp)
        testil.eq(hits, 3)
        testil.eq(wait_time / DAYS, 6)

        # After 6.333 days the threshold is met exactly
        hits, wait_time = counter.get_count_and_wait_time(
            scope, threshold=2, timestamp=timestamp + wait_time_days * DAYS
        )
        testil.eq(hits, 2)
        testil.eq(wait_time, 0.0)
