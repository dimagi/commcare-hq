import os
import sys
from unittest import SkipTest

from testil import Regex, assert_raises, eq

from corehq.util.test_utils import capture_log_output, timelimit
from .. import parallel as mod


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


@timelimit
def test_consume_error():
    class Error(Exception):
        pass

    with assert_raises(Error):
        for result in mod.Pool().imap_unordered(square, range(10)):
            raise Error
            # error should not cause deadlock


@timelimit
def test_produce_error():
    class Error(Exception):
        pass

    def producer():
        yield 1
        yield 2
        raise Error

    results = set()
    with assert_raises(Error):
        for result in mod.Pool().imap_unordered(square, producer()):
            results.add(result)
    eq(results, {1, 4})


def test_race_conditions():
    # This test is slow and is not very useful except for finding race
    # conditions which often result in a hung process.
    if not os.environ.get("TEST_PARALLEL"):
        raise SkipTest("set TEST_PARALLEL=1 to enable this test")

    # NOTE there is a bug somewhere in the tested code (possibly in
    # gipc or multiprocessing) that causes unreleased file handles to
    # accumulate. This test will fail with "OSError: [Errno 24] Too
    # many open files" if `iterations` is set too high. This has been
    # observed on macOS where `ulimit -n` is 256.
    iterations = 30
    tests = [
        test_parallel,
        test_initializer,
        test_maxtasksperchild,
        test_process_item_error,
        test_replace_dead_worker,
        test_consume_error,
    ]
    for x in range(iterations):
        for test in tests:
            yield test,


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
