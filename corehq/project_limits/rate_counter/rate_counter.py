import hashlib
import time

from django.core.cache import caches, DEFAULT_CACHE_ALIAS

from corehq.project_limits.rate_counter.interfaces import AbstractRateCounter

REDIS = caches[DEFAULT_CACHE_ALIAS]
LOCMEM = caches['locmem']


class SlidingWindowRateCounter(AbstractRateCounter):
    """
    A "Sliding Window Over Fixed Grains" approach that approximates perfect sliding window

    A perfect sliding window approach would require keeping the timestamp of every event
    and count the number that fall between now and now - window_duration;
    for lower memory and performance overhead we instead approximate that
    by dividing time up into fixed "grains", i.e. sub-windows,
    over which we slide the larger window.
    For the earliest grain which is sliding out of the window,
    we assume linear distribution of events over time, and thus compute its contribution
    to the total as (% overlap of grain with our window) * (events in grain).

    See a description of this approach (with grains_per_window=1) here:
    https://konghq.com/blog/how-to-design-a-scalable-rate-limiting-algorithm/

    """
    def __init__(self, key, window_duration, window_offset=0, grains_per_window=1,
                 memoize_timeout=15.0, _FixedWindowRateCounter=None):
        """

        :param key: short description of the window e.g. "week"
        :param window_duration: length of the window in seconds
        :param window_offset: offset from epoch of window boundary
        :param grains_per_window: How many grains the window should be divided into
            (higher number = more accuracy)
        :param memoize_timeout: how long to memoize the information in memory in seconds
            This is the upper limit on how long a `get` could return a stale value.
        """
        _FixedWindowRateCounter = _FixedWindowRateCounter or FixedWindowRateCounter
        self.key = key
        self.window_duration = window_duration
        self.window_offset = window_offset
        self.grains_per_window = grains_per_window
        self.memoize_timeout = memoize_timeout
        self.grain_duration = window_duration / grains_per_window
        self.grain_counter = _FixedWindowRateCounter(
            key=key,
            window_duration=self.grain_duration,
            window_offset=window_offset,
            keep_windows=grains_per_window + 1,
            memoize_timeout=memoize_timeout
        )

    def get(self, scope, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        counts = [
            self.grain_counter.get(scope, timestamp - i * self.grain_duration,
                                   key_is_active=(i == 0))
            for i in range(self.grains_per_window + 1)
        ]
        earliest_grain_count = counts.pop()
        # This is the percentage of the way through the current grain we are
        progress_in_current_grain = (timestamp % self.grain_duration) / self.grain_duration
        # This is the count from the percentage of the earliest grain that should count
        contribution_from_earliest = earliest_grain_count * (1 - progress_in_current_grain)
        return sum(counts) + contribution_from_earliest

    def retry_after(self):
        """Calculates the time (in seconds) left in the current grain"""
        timestamp = time.time()
        progress_in_current_grain = (timestamp % self.grain_duration) / self.grain_duration
        progress_left_in_grain = 1 - progress_in_current_grain
        return progress_left_in_grain * self.grain_duration

    def increment(self, scope, delta=1, timestamp=None):
        # this intentionally doesn't return because this is the active grain count,
        # not the total that would be returned by get
        self.grain_counter.increment(scope, delta, timestamp=timestamp)

    def increment_and_get(self, scope, delta=1, timestamp=None):
        self.increment(scope, delta, timestamp=timestamp)
        return self.get(scope, timestamp=timestamp)


class FixedWindowRateCounter(AbstractRateCounter):
    def __init__(self, key, window_duration, window_offset=0, keep_windows=1,
                 memoize_timeout=15.0, _CounterCache=None):
        """
        :param key: short description of the window e.g. "week"
        :param window_duration: length of the window in seconds
        :param window_offset: offset of window boundary in seconds from the epoch
        :param keep_windows: number of windows to retain (including current one)
        :param memoize_timeout: how long to memoize the information in memory in seconds
            This is the upper limit on how long a `get` could return a stale value.
        """
        _CounterCache = _CounterCache or CounterCache
        assert keep_windows >= 1
        self.key = key
        self.window_duration = window_duration
        self.window_offset = window_offset
        self.counter = _CounterCache(memoize_timeout, timeout=keep_windows * window_duration)

    @staticmethod
    def _digest(string):
        return hashlib.sha1(string.encode('utf-8')).hexdigest()

    def _cache_key(self, scope, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        if isinstance(scope, str):
            scope = (scope,)
        return self._digest('fwrc-{}-{}-{}'.format(
            self.key,
            ':'.join(map(self._digest, scope)),
            int((timestamp - self.window_offset) / self.window_duration)
        ))

    def get(self, scope, timestamp=None, key_is_active=True):
        return self.counter.get(self._cache_key(scope, timestamp=timestamp), key_is_active=key_is_active)

    def increment_and_get(self, scope, delta=1, timestamp=None):
        return self.counter.incr(self._cache_key(scope, timestamp=timestamp), delta)

    def increment(self, scope, delta=1, timestamp=None):
        self.increment_and_get(scope, delta, timestamp=timestamp)


class CounterCache(object):
    def __init__(self, memoized_timeout, timeout, local_cache=LOCMEM, shared_cache=REDIS):
        self.memoized_timeout = memoized_timeout
        self.timeout = int(timeout)
        self.local_cache = local_cache
        self.shared_cache = shared_cache

    def incr(self, key, delta=1):
        value = self.shared_cache.incr(key, delta, ignore_key_check=True)
        if value == 1:
            self.shared_cache.expire(key, timeout=self.timeout)
        self.local_cache.set(key, value, timeout=self.memoized_timeout)
        return value

    def get(self, key, key_is_active=True):
        """
        :param key: Cache key
        :param key_is_active: Whether you believe the key is being actively updated
            If not, then use the longer timeout for local memory cache as well.
        """
        local_timeout = self.memoized_timeout if key_is_active else self.timeout
        value = self.local_cache.get(key, default=None)
        if value is None:
            value = self.shared_cache.get(key, default=0)
            self.local_cache.set(key, value, timeout=local_timeout)
        assert value is not None
        return value
