import logging
from contextlib import contextmanager
from threading import RLock
from unittest.mock import patch

import attr

import dimagi.utils.couch as module

log = logging.getLogger(__name__)


def reentrant_redis_locks(test=None):
    """Decorator/context manager to enable reentrant redis locks

    This is useful for tests that do things like acquire a lock and then
    fire off a celery task (which will usually be executed synchronously
    in tests) before the lock is released.

    Usage as decorator:

        @reentrant_redis_locks
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

    @contextmanager
    def context():
        with patch.object(module, "get_redis_client", client):
            try:
                yield
            finally:
                assert not locks, f"unreleased {locks.values()}"

    locks = {}
    client = TestRedisClient(get_reentrant_lock)
    manager = context()
    return manager if test is None else manager(test)


@attr.s
class TestRedisClient:
    lock = attr.ib()

    def __call__(self):
        return self


@attr.s
class ReentrantTestLock:
    name = attr.ib()
    locks = attr.ib(repr=False)
    level = attr.ib(default=0, init=False)
    lock = attr.ib(factory=RLock, init=False, repr=False)

    def acquire(self, **kw):
        self.level += 1
        try:
            return self.lock.acquire(**kw)
        finally:
            log.debug("acquire %s [%s]", self.name, self.level)

    def release(self):
        self.level -= 1
        log.debug("release %s [%s]", self.name, self.level)
        if self.level <= 0:
            self.locks.pop(self.name, None)
        self.lock.release()
