from functools import wraps
from unittest import TestCase

from nose.plugins import PluginTester
from testil import eq

from .noseplugins import classcleanup as mod


class TestClassCleanupPlugin(PluginTester, TestCase):
    activate = ''  # Activate option not needed. Plugin is always enabled.
    plugins = [mod.ClassCleanupPlugin()]

    def setUp(self):
        pass  # super().setUp() is called by self.run_with_errors(...)

    def makeSuite(self):
        class Test(TestCase):
            @classmethod
            @maybe_error(self)
            def setUpClass(cls):
                cls.addClassCleanup(lambda: self.result.append("cleanup"))

            @maybe_error(self)
            def setUp(self):
                pass

            @maybe_error(self)
            def runTest(self):
                pass

            @maybe_error(self)
            def tearDown(self):
                pass

            @classmethod
            @maybe_error(self)
            def tearDownClass(cls):
                pass

        return [Test()]

    def run_with_errors(self, *errors, error_class=Exception):
        self.errors = errors
        self.result = []
        self.error_class = error_class
        super().setUp()

    def test_cleanup_in_happy_path(self):
        self.run_with_errors()
        eq(self.result, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown",
            "tearDownClass",
            "cleanup",
        ])

    def test_cleanup_on_error_in_set_up_class(self):
        self.run_with_errors("setUpClass")
        eq(self.result, [
            "setUpClass Exception",
            "cleanup"
        ])

    def test_cleanup_on_error_in_set_up(self):
        self.run_with_errors("setUp")
        eq(self.result, [
            "setUpClass",
            "setUp Exception",
            "tearDownClass",
            "cleanup",
        ])

    def test_cleanup_on_error_in_test(self):
        self.run_with_errors("runTest")
        eq(self.result, [
            "setUpClass",
            "setUp",
            "runTest Exception",
            "tearDown",
            "tearDownClass",
            "cleanup",
        ])

    def test_cleanup_on_test_fail(self):
        self.run_with_errors("runTest", error_class=AssertionError)
        eq(self.result, [
            "setUpClass",
            "setUp",
            "runTest AssertionError",
            "tearDown",
            "tearDownClass",
            "cleanup",
        ])

    def test_cleanup_on_error_in_tearDown(self):
        self.run_with_errors("tearDown")
        eq(self.result, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown Exception",
            "tearDownClass",
            "cleanup",
        ])

    def test_cleanup_on_error_in_tearDownClass(self):
        self.run_with_errors("tearDownClass")
        eq(self.result, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown",
            "tearDownClass Exception",
            "cleanup",
        ])

    def test_cleanup_on_error_in_tearDown_and_tearDownClass(self):
        self.run_with_errors("tearDown", "tearDownClass")
        eq(self.result, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown Exception",
            "tearDownClass Exception",
            "cleanup",
        ])


def maybe_error(test):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            func(self)
            test.result.append(func.__name__)
            if func.__name__ in test.errors:
                test.result[-1] += f" {test.error_class.__name__}"
                raise test.error_class
        return wrapper
    return decorator
