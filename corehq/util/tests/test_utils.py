import re
import time

from unittest import TestCase

from testil import assert_raises, eq

from ..test_utils import disable_quickcache, generate_cases, timelimit


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


def test_disable_quickcache():
    from corehq.util.quickcache import quickcache

    @quickcache(["arg"])
    def foo(arg):
        calls.append(arg)
        return arg

    calls = []
    try:
        with disable_quickcache():
            eq(foo(1), 1)
            eq(foo(1), 1)
            eq(foo.get_cached_value(1), Ellipsis)
            eq(calls, [1, 1])

        # cache should be re-enabled on exit disabled context
        eq(foo(2), 2)
        eq(foo(2), 2)
        eq(calls, [1, 1, 2])
        eq(foo.get_cached_value(2), 2)
    finally:
        foo.clear(1)
        foo.clear(2)


def test_generate_cases_for_test_method():
    # Preferred usage pattern
    class Test(TestCase):
        @generate_cases([
            (1,),
            (2,),
        ])
        def test(self, arg):
            return str(arg)

    assert not hasattr(Test, "test"), Test.test
    check_case(Test)


def test_generate_cases_for_class():
    # Deprecated usage pattern
    class Test(TestCase):
        pass

    @generate_cases([
        (1,),
        (2,),
    ], Test)
    def test(self, arg):
        return str(arg)

    eq(test, None)
    check_case(Test)


def test_generate_cases_for_function():
    # Deprecated usage pattern
    @generate_cases([
        (1,),
        (2,),
    ])
    def test(self, arg):
        return str(arg)

    assert issubclass(test, TestCase), test.__mro__
    check_case(test)


def check_case(Test):
    test_case = Test()
    for arg in [1, 2]:
        name = f"test({arg},)"
        test = getattr(test_case, name, None)
        assert test is not None, (name, dir(test_case))
        eq(test(), str(arg))
