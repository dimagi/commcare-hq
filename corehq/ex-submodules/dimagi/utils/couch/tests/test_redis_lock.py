import uuid

from redis.lock import Lock as RedisLock

from dimagi.utils.couch import get_redis_lock

from corehq.tests.noseplugins.redislocks import TestLock
from corehq.util.metrics.lockmeter import MeteredLock


def test_get_redis_lock_with_token():
    lock_name = 'test-1'
    metered_lock = get_redis_lock(key=lock_name, name=lock_name, timeout=1)
    assert isinstance(metered_lock, MeteredLock)
    # metered_lock.lock is a TestLock instance because of
    # corehq.tests.noseplugins.redislocks.RedisLockTimeoutPlugin
    test_lock = metered_lock.lock
    assert isinstance(test_lock, TestLock)
    redis_lock = test_lock.lock
    assert isinstance(redis_lock, RedisLock)

    token = uuid.uuid1().hex
    acquired = redis_lock.acquire(blocking=False, token=token)
    assert acquired

    # What we want to be able to do in a separate process:
    metered_lock_2 = get_redis_lock(key=lock_name, name=lock_name, timeout=1)
    redis_lock_2 = metered_lock_2.lock.lock
    redis_lock_2.local.token = token
    # Does not raise LockNotOwnedError:
    redis_lock_2.release()
