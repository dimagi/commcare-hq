import logging
from contextlib import contextmanager
from threading import Lock, RLock
from unittest.mock import MagicMock, patch

import attr

log = logging.getLogger(__name__)
_LOCK = Lock()


@contextmanager
def reentrant_redis_locks():
    """Decorator/context manager to enable reentrant redis locks

    This is useful for tests that do things like acquire a lock and
    then, before the lock is released, fire off a celery task (which
    will usually be executed synchronously due to
    `CELERY_TASK_ALWAYS_EAGER`) that acquires the same lock.

    Note: the use of `RLock` internalizes the lock to the test process
    (unlike redis locks, which are inter-process) and therefore assumes
    that each test process is fully isolated and has its own dedicated
    database cluster. In other words, this will not work if multiple
    test processes need synchronized access to a single shared database
    cluster.

    Usage as decorator:

        @reentrant_redis_locks()
        def test_something():
            ...

    Usage as context manager:

        def test_something():
            with reentrant_redis_locks():
                ...
    """
    def get_reentrant_lock(key, **kw):
        try:
            lock = locks[key]
        except KeyError:
            lock = locks[key] = ReentrantTestLock(key, locks)
        return lock

    locks = {}
    client = TestRedisClient(get_reentrant_lock)
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError("nested/concurrent reentrant_redis_locks()")
    try:
        with patch("dimagi.utils.couch.get_redis_client", client):
            yield
    finally:
        _LOCK.release()
    assert not locks, f"unreleased {locks.values()}"


@contextmanager
def real_redis_client():
    global _mock_redis_client
    try:
        _mock_redis_client = False
        yield
    finally:
        _mock_redis_client = True


_mock_redis_client = True


@attr.s
class TestRedisClient:
    lock = attr.ib()

    def __call__(self):
        return self

    @property
    def client(self):
        if _mock_redis_client:
            return MagicMock()
        from dimagi.utils.couch.cache.cache_core import get_redis_client
        return get_redis_client().client


@attr.s
class ReentrantTestLock:
    name = attr.ib()
    locks = attr.ib(repr=False)
    level = attr.ib(default=0, init=False)
    lock = attr.ib(factory=RLock, init=False, repr=False)

    def acquire(self, **kw):
        timeout_added = kw.get("blocking", True) and "timeout" not in kw
        if timeout_added:
            kw["timeout"] = 10
        self.level += 1
        try:
            acquired = self.lock.acquire(**kw)
            if not acquired and timeout_added:
                # caller expected to block indefinitely,
                raise RuntimeError(f"could not acquire lock: {self.name}")
            return acquired
        finally:
            log.debug("acquire %s [%s]", self.name, self.level)

    def release(self):
        self.level -= 1
        log.debug("release %s [%s]", self.name, self.level)
        if self.level <= 0:
            self.locks.pop(self.name, None)
        self.lock.release()
