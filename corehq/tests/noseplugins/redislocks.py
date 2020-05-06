import logging
from datetime import datetime

import attr
from nose.tools import nottest
from nose.plugins import Plugin

import dimagi.utils.couch
from dimagi.utils.couch.cache.cache_core import get_redis_client

from ..locks import TestRedisClient

log = logging.getLogger(__name__)


class RedisLockTimeoutPlugin(Plugin):
    """A plugin that causes blocking redis locks to error on lock timeout"""
    name = "test-redis-locks"
    enabled = True

    def configure(self, options, conf):
        """Do not call super (always enabled)"""
        self.get_client = TestRedisClient(get_test_lock)

    def begin(self):
        """Patch redis client used for locks before any tests are run

        The patch will remain in effect for the duration of the test
        process. Tests (e.g., using `reentrant_redis_locks`) may
        override this patch temporarily on an as-needed basis.
        """
        dimagi.utils.couch.get_redis_client = self.get_client

    def stopTest(self, case):
        get = dimagi.utils.couch.get_redis_client
        assert get == self.get_client, f"redis client patch broke ({get})"


@nottest
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
