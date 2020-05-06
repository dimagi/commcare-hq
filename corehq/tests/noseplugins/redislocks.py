import logging
from datetime import datetime
from threading import Lock
from unittest.mock import patch

import attr
from nose.plugins import Plugin

from dimagi.utils.couch.cache.cache_core import get_redis_client

from .uniformresult import uniform_description
from ..locks import TestRedisClient

log = logging.getLogger(__name__)
_LOCK = Lock()


class RedisLockTimeoutPlugin(Plugin):
    """A plugin that causes blocking redis locks to error on lock timeout"""
    name = "test-redis-locks"
    enabled = True

    def configure(self, options, conf):
        """Do not call super (always enabled)"""
        client = TestRedisClient(get_test_lock)
        self.patch = patch("dimagi.utils.couch.get_redis_client", client)

    def startTest(self, case):
        assert _LOCK.acquire(blocking=False), \
            f"{uniform_description(case.test)}: concurrent tests not supported"
        self.patch.start()

    def stopTest(self, case):
        self.patch.stop()
        _LOCK.release()


def get_test_lock(key, **kw):
    timeout = kw["timeout"]
    lock = get_redis_client().lock(key, **kw)
    return TestLock(key, lock, timeout)


@attr.s
class TestLock:
    name = attr.ib()
    lock = attr.ib(repr=False)
    timeout = attr.ib()

    def acquire(self, **kw):
        start = datetime.now()
        log.info("acquire %s", self)
        try:
            return self.lock.acquire(**kw)
        finally:
            elapsed = datetime.now() - start
            if elapsed.total_seconds() > self.timeout / 2:
                self.release()
                raise TimeoutError(f"locked for {elapsed} (timeout={self.timeout}s)")

    def release(self):
        log.info("release %s", self)
        self.lock.release()

    def __enter__(self):
        self.acquire(blocking=True)

    def __exit__(self, *exc_info):
        self.release()


class TimeoutError(Exception):
    """Error raised when lock timeout is approached during tests"""
