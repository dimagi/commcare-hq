"""A plugin that causes blocking redis locks to error on lock timeout"""
import logging
from datetime import datetime

import attr
import pytest

from ..locks import TestRedisClient
from ..tools import nottest

log = logging.getLogger(__name__)


@pytest.hookimpl
def pytest_sessionstart():
    import dimagi.utils.couch

    global get_client
    get_client = TestRedisClient(get_test_lock)

    # Patch redis client used for locks before any tests are run.
    # The patch will remain in effect for the duration of the test
    # process. Tests (e.g., using `reentrant_redis_locks`) may
    # override this patch temporarily on an as-needed basis.
    dimagi.utils.couch.get_redis_client = get_client


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown():
    result = yield
    import dimagi.utils.couch
    get = dimagi.utils.couch.get_redis_client
    assert get == get_client, f"redis client patch broke ({get})"
    return result


def get_test_lock(key, **kw):
    from dimagi.utils.couch.cache.cache_core import get_redis_client
    timeout = kw["timeout"]
    lock = get_redis_client().lock(key, **kw)
    return TestLock(key, lock, timeout)


@nottest
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
