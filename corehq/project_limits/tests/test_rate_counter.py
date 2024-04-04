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

    def test_sliding_window_get_count_and_wait_time_basic(self):
        timestamp = 1000 * 7 * DAYS

        counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS, grains_per_window=7)
        counter.grain_counter.counter.shared_cache.clear()

        counter.increment('alice', timestamp=timestamp)
        counter.increment('alice', timestamp=timestamp)

        hits, wait_time = counter.get_count_and_wait_time('alice', threshold=1, timestamp=timestamp)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 6.5)

        hits, wait_time = counter.get_count_and_wait_time('alice', threshold=1, timestamp=timestamp + 6.5 * DAYS)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 0.5)

        hits, wait_time = counter.get_count_and_wait_time('alice', threshold=2, timestamp=timestamp)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 7)

        hits, wait_time = counter.get_count_and_wait_time('alice', threshold=2, timestamp=timestamp + 7 * DAYS)
        testil.eq(hits, 2)
        testil.eq(wait_time / DAYS, 0)

    def test_sliding_window_get_count_and_wait_time_complex(self):
        timestamp = 1000 * 7 * DAYS

        counter = _SlidingWindowRateCounter('test-sliding-week', 7 * DAYS, grains_per_window=7)
        counter.grain_counter.counter.shared_cache.clear()

        counter.increment('alice', timestamp=timestamp)
        counter.increment('alice', timestamp=timestamp)

        counter.increment('alice', timestamp=timestamp + 1 * DAYS)
        counter.increment('alice', timestamp=timestamp + 1 * DAYS)

        hits, wait_time = counter.get_count_and_wait_time('alice', threshold=4, timestamp=timestamp + 2 * DAYS)
        testil.eq(hits, 4)
        testil.eq(wait_time / DAYS, 5)

        hits, wait_time = counter.get_count_and_wait_time('alice', threshold=2, timestamp=timestamp + 7 * DAYS)
        testil.eq(hits, 4)
        testil.eq(wait_time / DAYS, 1)
