import re
import time

from testil import assert_raises, eq

from ..timelimit import timelimit


def test_timelimit_pass():
    @timelimit(0.001)
    def addone(x):
        return x + 1
    eq(addone(x=1), 2)


def test_timelimit_fail():
    @timelimit(0.0001)
    def sleeper():
        time.sleep(0.001)
    with assert_raises(AssertionError, msg=re.compile("sleeper time limit .+ exceeded")):
        sleeper()


def test_timelimit_default():
    @timelimit
    def double(x):
        return x * 2
    eq(double(2), 4)


def test_nested_timelimits():
    @timelimit(0.01)
    def sleeper():
        time.sleep(0.002)

    @timelimit(0.001)
    def addone(x):
        sleeper()
        return x + 1

    eq(addone(x=1), 2)


def test_nested_timelimit_failure():
    @timelimit(0.001)
    def inner():
        time.sleep(0.002)

    @timelimit(0.01)
    def outer():
        inner()

    with assert_raises(AssertionError, msg=re.compile("inner time limit .+ exceeded")):
        outer()


def test_nested_timelimits_with_error():
    @timelimit
    def raiser():
        raise ValueError("boom")

    with assert_raises(ValueError, msg="boom"):
        raiser()

    # time limit of raiser should not transfer to this timelimit
    @timelimit(0.001)
    def too_slow():
        time.sleep(0.0011)

    with assert_raises(AssertionError, msg=re.compile("too_slow time limit .+ exceeded")):
        too_slow()


def test_cannot_limit_generator():
    with assert_raises(ValueError, msg=re.compile("'timelimit' on generator")):
        @timelimit
        def gen():
            yield
