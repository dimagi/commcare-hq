import gevent
from gevent.pool import Pool
from greenlet import GreenletExit
from testil import assert_raises, eq

from .. import util as mod


def test_exit_on_error():
    @mod.exit_on_error
    def fail():
        raise Exception("stop!")

    with assert_raises(mod.UnhandledError, msg="stop!"):
        job = gevent.spawn(fail)
        gevent.wait([job])


def test_exit_on_error_greenlet_exit():
    @mod.exit_on_error
    def stop():
        raise GreenletExit

    # should not raise GreenletExit
    job = gevent.spawn(stop)
    gevent.wait([job])


def test_wait_for_one_task_to_complete():
    n = 3
    pool = Pool(size=n)
    for x in range(n):
        pool.spawn(gevent.sleep)
    eq(len(pool), n)
    mod.wait_for_one_task_to_complete(pool)
    eq(len(pool), n - 1)


def test_wait_for_one_task_to_complete_on_empty_pool():
    pool = Pool(size=3)
    with assert_raises(ValueError):
        mod.wait_for_one_task_to_complete(pool)
