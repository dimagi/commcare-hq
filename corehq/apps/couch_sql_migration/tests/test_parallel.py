import os
import sys
from unittest import SkipTest

from testil import Regex, assert_raises, eq

from corehq.util.test_utils import capture_log_output

from corehq.util.test_utils import timelimit
from .. import parallel as mod


def setup_module():
    if not os.environ.get("TEST_PARALLEL"):
        raise SkipTest("""
            These tests hang intermittently due to a race condition
            somewhere in the tested code. Be sure to run them locally
            when modifying the code since they are disabled on Travis.
        """)


@timelimit
def test_parallel():
    results = set(mod.Pool().imap_unordered(square, range(10)))
    eq(results, {x * x for x in range(10)})


@timelimit
def test_initializer():
    data = {2: "two", 4: "four"}
    pool = mod.Pool(initializer=init_data, initargs=(data,))
    results = set(pool.imap_unordered(get_data, range(5)))
    eq(results, {None, "one", "two", None, "four"})


@timelimit
def test_maxtasksperchild():
    pool = mod.Pool(processes=2, maxtasksperchild=2)
    results = list(pool.imap_unordered(pid_val, range(5)))
    pids = {r[0] for r in results}
    eq(len(pids), 3, results)


@timelimit
def test_process_item_error():
    with capture_log_output(mod.__name__) as log:
        results = set(mod.Pool().imap_unordered(one_over, [-1, 0, 1]))
    logs = log.get_output()
    eq(logs, Regex("error processing item in worker"))
    eq(logs, Regex("ZeroDivisionError"))
    eq(results, {-1, 1})


@timelimit
def test_replace_dead_worker():
    pool = mod.Pool(processes=2)
    with capture_log_output(mod.__name__) as log:
        results = list(pool.imap_unordered(die, range(3)))
    logs = log.get_output()
    eq(logs.count("replaced worker"), 3, logs)
    eq(results, [])


def test_pool_processes_validator():
    with assert_raises(ValueError, msg="one or more processes required, got 0"):
        mod.Pool(processes=0)


def square(value):
    return value ** 2


def one_over(value):
    return 1 / value


def die(value):
    sys.exit(1)


def pid_val(value):
    return os.getpid(), value


def get_data(key):
    return worker_data.get(key)


def init_data(extra_data):
    worker_data.update(extra_data)


worker_data = {1: "one"}
