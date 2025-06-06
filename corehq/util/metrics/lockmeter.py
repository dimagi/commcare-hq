import time

from corehq.util.metrics import metrics_counter, metrics_histogram_timer


class MeteredLock(object):
    """A lock wrapper that measures various lock characteristics

    This was built for profiling Redis locks, but should work with any
    type of lock that has `acquire()` and `release()` methods.
    """

    timing_buckets = (0.1, 1, 5, 10, 30, 60, 120, 60 * 5, 60 * 10, 60 * 15, 60 * 30)

    def __init__(self, lock, name, track_unreleased=True):
        self.lock = lock
        self.tags = {"lock_name": name}
        self.name = name
        self.key = lock.name
        self.lock_timer = metrics_histogram_timer(
            "commcare.lock.locked_time", self.timing_buckets
        )
        self.track_unreleased = track_unreleased
        self.end_time = None

    def acquire(self, *args, **kw):
        buckets = self.timing_buckets
        with metrics_histogram_timer("commcare.lock.acquire_time", buckets):
            acquired = self.lock.acquire(*args, **kw)
        if acquired:
            timeout = getattr(self.lock, "timeout", None)
            if timeout:
                self.end_time = time.time() + timeout
            self.lock_timer.start()
        return acquired

    def reacquire(self):
        buckets = self.timing_buckets
        with metrics_histogram_timer("commcare.lock.reacquire_time", buckets):
            acquired = self.lock.reacquire()
        if acquired:
            self.end_time = time.time() + self.lock.timeout
            self.lock_timer.start()
        return acquired

    def release(self):
        self.lock.release()
        if self.lock_timer.is_started():
            self.lock_timer.stop()
        if self.end_time and time.time() > self.end_time:
            metrics_counter("commcare.lock.released_after_timeout", tags=self.tags)

    @property
    def local(self):
        # Used for setting lock token
        # Raises AttributeError if lock does not have a `local` attribute
        return self.lock.local

    def __enter__(self):
        self.acquire(blocking=True)
        return self

    def __exit__(self, *exc_info):
        self.release()

    def __del__(self):
        if self.track_unreleased and self.lock_timer.is_started():
            metrics_counter("commcare.lock.not_released", tags=self.tags)

    def release_failed(self):
        """Indicate that the lock was not released"""
        metrics_counter("commcare.lock.release_failed", tags=self.tags)

    def degraded(self):
        """Indicate that the lock has "degraded gracefully"

        The lock was not acquired, but processing continued as if it had
        been acquired.
        """
        metrics_counter("commcare.lock.degraded", tags=self.tags)
