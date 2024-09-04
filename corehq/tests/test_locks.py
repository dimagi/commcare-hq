import re
from redis.exceptions import LockError
from testil import assert_raises, eq

from dimagi.utils.couch import get_redis_lock

from corehq.util.test_utils import timelimit

from .locks import ReentrantTestLock, reentrant_redis_locks
from .pytest_plugins.redislocks import TestLock, TimeoutError


def test_redislocks_pytest_plugin():
    lock1 = get_redis_lock(__name__, timeout=0.2, name="test")
    assert isinstance(lock1.lock, TestLock), lock1.lock
    assert lock1.acquire(blocking_timeout=1)
    lock2 = get_redis_lock(__name__, timeout=0.2, name="test")
    with assert_raises(TimeoutError):
        assert lock2.acquire(blocking_timeout=1)
    with assert_raises(LockError, msg="Cannot release a lock that's no longer owned"):
        lock1.release()


@reentrant_redis_locks()
def test_nested_reentrant_redis_locks_is_not_allowed():
    with assert_raises(RuntimeError):
        with reentrant_redis_locks():
            pass


@timelimit(0.1)
def test_reentrant_redis_locks():
    with reentrant_redis_locks():
        simulate_reentrant_lock()


@timelimit(0.1)
@reentrant_redis_locks()
def test_reentrant_redis_locks_decorator():
    simulate_reentrant_lock()


def simulate_reentrant_lock():
    lock1 = get_redis_lock(__name__, timeout=0.5, name="test")
    lock2 = get_redis_lock(__name__, timeout=0.5, name="test")
    assert isinstance(lock1.lock, ReentrantTestLock), lock1.lock
    assert isinstance(lock2.lock, ReentrantTestLock), lock2.lock
    with lock1, lock2:
        pass  # no deadlock, no errors


@timelimit(0.1)
def test_unreleased_lock():
    msg = "unreleased dict_values([ReentrantTestLock(name='unreleased', level=1)])"
    with assert_raises(AssertionError, msg=re.compile("^" + re.escape(msg))):
        with reentrant_redis_locks():
            lock = get_redis_lock("unreleased", timeout=0.5, name="test")
            assert lock.acquire()
    lock.release()


#@timelimit(0.1)
#def test_extra_lock_release():
#    with reentrant_redis_locks():
#        lock = get_redis_lock("extra_release", timeout=0.5, name="test")
#        assert lock.acquire()
#        lock.release()
#        with assert_raises(RuntimeError):
#            lock.release()


def test_decorator_name():
    @reentrant_redis_locks()
    def fake_test():
        pass
    eq(fake_test.__name__, "fake_test")
