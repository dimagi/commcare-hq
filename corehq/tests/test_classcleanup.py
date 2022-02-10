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

        def log_call_and_maybe_error(func):
            @wraps(func)
            def wrapper(self_):
                func(self_)
                self.call_log.append(func.__name__)
                if func.__name__ in self.errors:
                    self.call_log[-1] += f" {self.error_class.__name__}"
                    raise self.error_class
            return wrapper

        class Test(TestCase):
            @classmethod
            @log_call_and_maybe_error
            def setUpClass(cls):
                cls.addClassCleanup(self.call_log.append, "classCleanup")

            @log_call_and_maybe_error
            def setUp(self):
                pass

            @log_call_and_maybe_error
            def runTest(self):
                pass

            @log_call_and_maybe_error
            def tearDown(self):
                pass

            @classmethod
            @log_call_and_maybe_error
            def tearDownClass(cls):
                pass

        return [Test()]

    def run_with_errors(self, *errors, error_class=Exception):
        self.call_log = []
        self.errors = errors
        self.error_class = error_class
        super().setUp()

    def test_cleanup_in_happy_path(self):
        self.run_with_errors()
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown",
            "tearDownClass",
            "classCleanup",
        ])

    def test_cleanup_on_error_in_set_up_class(self):
        self.run_with_errors("setUpClass")
        eq(self.call_log, [
            "setUpClass Exception",
            "classCleanup"
        ])

    def test_cleanup_on_error_in_set_up(self):
        self.run_with_errors("setUp")
        eq(self.call_log, [
            "setUpClass",
            "setUp Exception",
            "tearDownClass",
            "classCleanup",
        ])

    def test_cleanup_on_error_in_test(self):
        self.run_with_errors("runTest")
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest Exception",
            "tearDown",
            "tearDownClass",
            "classCleanup",
        ])

    def test_cleanup_on_test_fail(self):
        self.run_with_errors("runTest", error_class=AssertionError)
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest AssertionError",
            "tearDown",
            "tearDownClass",
            "classCleanup",
        ])

    def test_cleanup_on_error_in_tearDown(self):
        self.run_with_errors("tearDown")
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown Exception",
            "tearDownClass",
            "classCleanup",
        ])

    def test_cleanup_on_error_in_tearDownClass(self):
        self.run_with_errors("tearDownClass")
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown",
            "tearDownClass Exception",
            "classCleanup",
        ])

    def test_cleanup_on_error_in_tearDown_and_tearDownClass(self):
        self.run_with_errors("tearDown", "tearDownClass")
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown Exception",
            "tearDownClass Exception",
            "classCleanup",
        ])
