from __future__ import annotations

import time
from types import TracebackType
from typing import Any, Optional, Type, cast

from ddtrace import Span, tracer

from . import metrics_counter, metrics_histogram_timer
from .typing import LockProto


class MeteredLock(object):
    """A lock wrapper that measures various lock characteristics

    This was built for profiling Redis locks, but should work with any
    type of lock that has `acquire()` and `release()` methods.
    """

    timing_buckets = (0.1, 1, 5, 10, 30, 60, 120, 60 * 5, 60 * 10, 60 * 15, 60 * 30)

    def __init__(
        self,
        lock: LockProto,
        name: str,
        track_unreleased: bool = True,
    ) -> None:
        self.lock = lock
        self.tags = {"lock_name": name}
        self.name = name
        self.key = lock.name
        self.lock_timer = metrics_histogram_timer(
            "commcare.lock.locked_time", self.timing_buckets
        )
        self.track_unreleased = track_unreleased
        self.end_time: Optional[float] = None
        self.lock_trace: Optional[Span] = None

    def acquire(self, *args: Any, **kw: Any) -> bool:
        buckets = self.timing_buckets
        with metrics_histogram_timer("commcare.lock.acquire_time", buckets), \
                tracer.trace("commcare.lock.acquire", resource=self.key) as span:
            acquired = self.lock.acquire(*args, **kw)
            span.set_tags({
                "key": self.key,
                "name": self.name,
                "acquired": ("true" if acquired else "false"),
            })
        if acquired:
            timeout = getattr(self.lock, "timeout", None)
            if timeout:
                self.end_time = time.time() + timeout
            self.lock_timer.start()
            if self.track_unreleased:
                self.lock_trace = tracer.trace("commcare.lock.locked", resource=self.key)
                self.lock_trace.set_tags({"key": self.key, "name": self.name})
        return acquired

    def release(self) -> None:
        self.lock.release()
        if self.lock_timer.is_started():
            self.lock_timer.stop()
        if self.end_time and time.time() > self.end_time:
            metrics_counter("commcare.lock.released_after_timeout", tags=self.tags)
        if self.lock_trace is not None:
            self.lock_trace.finish()
            self.lock_trace = None

    def __enter__(self) -> MeteredLock:
        self.acquire(blocking=True)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.release()

    def __del__(self) -> None:
        if self.track_unreleased and self.lock_timer.is_started():
            metrics_counter("commcare.lock.not_released", tags=self.tags)
        if self.lock_trace is not None:
            self.lock_trace.set_tag("deleted", "not_released")
            self.lock_trace.finish()
            self.lock_trace = None

    def release_failed(self) -> None:
        """Indicate that the lock was not released"""
        metrics_counter("commcare.lock.release_failed", tags=self.tags)

    def degraded(self) -> None:
        """Indicate that the lock has "degraded gracefully"

        The lock was not acquired, but processing continued as if it had
        been acquired.
        """
        metrics_counter("commcare.lock.degraded", tags=self.tags)
