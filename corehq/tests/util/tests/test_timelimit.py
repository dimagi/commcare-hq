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
    with assert_raises(AssertionError, msg=re.compile("sleeper took too long")):
        sleeper()


def test_timelimit_default():
    @timelimit
    def double(x):
        return x * 2
    eq(double(2), 4)
