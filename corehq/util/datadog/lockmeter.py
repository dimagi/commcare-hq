from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.util.datadog.gauges import datadog_counter, datadog_bucket_timer


class LockMeter(object):
    """A lock wrapper that measures various lock characteristics

    This was built for profiling Redis locks, but will for any type of
    lock that has `acquire()` and `release()` methods.
    """

    timing_buckets = (0.1, 1, 5, 10, 30, 60, 120, 60 * 5, 60 * 10, 60 * 15, 60 * 30)

    def __init__(self, lock, name):
        self.lock = lock
        self.tags = ["name:%s" % name]
        self.lock_timer = datadog_bucket_timer(
            "commcare.lock.locked_time", self.tags, self.timing_buckets)

    def acquire(self, *args, **kw):
        tags = self.tags
        buckets = self.timing_buckets
        with datadog_bucket_timer("commcare.lock.acquire_time", tags, buckets):
            acquired = self.lock.acquire(*args, **kw)
        if acquired:
            self.lock_timer.start()
        return acquired

    def release(self):
        self.lock.release()
        if self.lock_timer.is_started():
            self.lock_timer.stop()

    def __enter__(self):
        self.acquire(blocking=True)
        return self

    def __exit__(self, *exc_info):
        self.release()

    def __del__(self):
        if self.lock_timer.is_started():
            datadog_counter("commcare.lock.not_released", tags=self.tags)

    def release_failed(self):
        """Indicate that the lock was not released"""
        datadog_counter("commcare.lock.release_failed", tags=self.tags)

    def degraded(self):
        """Indicate that the lock has "degraded gracefully"

        The lock was not acquired, but processing continued as if it had
        been acquired.
        """
        datadog_counter("commcare.lock.degraded", tags=self.tags)
