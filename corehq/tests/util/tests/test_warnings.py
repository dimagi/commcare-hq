import warnings
from difflib import unified_diff
from functools import wraps
from unittest import TestCase, TestResult as Result, TestSuite as Suite
from unittest.mock import patch

from testil import Regex, assert_raises, eq

from ..warnings import filter_warnings
from corehq.warnings import original_warn


def verify_same_filters_before_and_after(test):
    @wraps(test)
    def check():
        old_filters = list(warnings.filters)
        with filter_warnings("error"), patch.object(warnings, "warn", original_warn):
            test()
            done = True
        assert done, "test did not return"
        if warnings.filters != old_filters:
            assert False, "warnings.filters changed\n" + "\n".join(unified_diff(
                [str(f) for f in old_filters],
                [str(f) for f in warnings.filters],
                "filters removed",
                "filters added",
                n=1,
            ))
    return check


def test_repr():
    eq(
        str(filter_warnings("default")),
        "filter_warnings('default', '', <class 'Warning'>, '', 0, False)",
    )


@verify_same_filters_before_and_after
def test_context_manager():
    with filter_warnings("default", "expected") as log:
        warnings.warn("expected", DeprecationWarning)
    eq([str(r.message) for r in log], ["expected"])


@verify_same_filters_before_and_after
def test_reentrant_context_manager():
    context = filter_warnings("default", "expected")
    with context as log1:
        warnings.warn("expected", DeprecationWarning)
    with context as log2:
        warnings.warn("expected too", DeprecationWarning)
    eq([str(r.message) for r in log1], ["expected"])
    eq([str(r.message) for r in log2], ["expected too"])


@verify_same_filters_before_and_after
def test_context_manager_with_ignored_warning():
    with filter_warnings("ignore", "fake") as log:
        warnings.warn("fake deprecation", DeprecationWarning)
    eq(log, [])


@verify_same_filters_before_and_after
def test_context_manager_with_unexpected_warning():
    with assert_raises(DeprecationWarning, msg="unexpected"):
        with filter_warnings("default", "nomatch") as log:
            warnings.warn("unexpected", DeprecationWarning)
    eq(log, [])


@verify_same_filters_before_and_after
def test_function_decorator():
    @filter_warnings("default", "expected")
    def func():
        warnings.warn("expected", DeprecationWarning)
        calls.append(1)
    calls = []
    func()
    eq(calls, [1])


@verify_same_filters_before_and_after
def test_function_decorator_with_unexpected_warning():
    @filter_warnings("default", "nomatch")
    def func():
        warnings.warn("unexpected", DeprecationWarning)
    with assert_raises(DeprecationWarning, msg="unexpected"):
        func()


@verify_same_filters_before_and_after
def test_class_decorator():
    @filter_warnings("default", "expected")
    class Test(TestCase):
        @classmethod
        def setUpClass(cls):
            warnings.warn("expected", DeprecationWarning)
            log.append("setup")
            super().setUpClass()

        @classmethod
        def tearDownClass(cls):
            warnings.warn("expected", DeprecationWarning)
            super().tearDownClass()
            log.append("teardown")

        def runTest(self):
            warnings.warn("expected", DeprecationWarning)
            log.append("test")

    log = []
    Suite([Test()]).debug()
    eq(log, ["setup", "test", "teardown"])


@verify_same_filters_before_and_after
def test_class_decorator_should_not_catch_unfiltered_setup_warning():
    @filter_warnings("default", "message", DeprecationWarning)
    class Test(TestCase):
        @classmethod
        def setUpClass(cls):
            log.append("setup")
            warnings.warn("fail")
            log.append("setup end")  # should not get here

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()
            log.append("teardown")

        def runTest(self):
            log.append("test")

    log = []
    result = Result()
    Suite([Test()]).run(result)
    eq(str(result.errors), Regex(r" in setUpClass\\n .*Warning: fail"), result)
    eq(log, ["setup"])


@verify_same_filters_before_and_after
def test_class_decorator_should_not_catch_unfiltered_test_warning():
    @filter_warnings("default", "message", DeprecationWarning)
    class Test(TestCase):
        @classmethod
        def setUpClass(cls):
            log.append("setup")
            super().setUpClass()

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()
            log.append("teardown")

        def runTest(self):
            warnings.warn("fail")
            log.append("test")  # should not get here

    log = []
    result = Result()
    Suite([Test()]).run(result)
    eq(str(result.errors), Regex(r" in runTest\\n .*Warning: fail"), result)
    eq(log, ["setup", "teardown"])


@verify_same_filters_before_and_after
def test_class_decorator_should_not_catch_unfiltered_teardown_warning():
    @filter_warnings("default", "message", DeprecationWarning)
    class Test(TestCase):
        @classmethod
        def setUpClass(cls):
            log.append("setup")
            super().setUpClass()

        @classmethod
        def tearDownClass(cls):
            warnings.warn("fail")
            log.append("teardown")

        def runTest(self):
            log.append("test")  # should not get here

    log = []
    result = Result()
    Suite([Test()]).run(result)
    eq(str(result.errors), Regex(r" in tearDownClass\\n .*Warning: fail"), result)
    eq(log, ["setup", "test"])
