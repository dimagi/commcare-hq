import inspect
import os

from testil import eq
from unmagic import fixture

pytest_plugins = ["pytester"]
log = []


class TestClassCleanupPlugin:

    def run_suite(self, **kwargs):
        @get_source
        def test_py():
            from functools import wraps
            from unittest import TestCase

            import corehq.tests.test_classcleanup as mod

            def log(value):
                mod.log.append(value)

            def log_call_and_maybe_error(func):
                @wraps(func)
                def wrapper(self_):
                    func(self_)
                    if func.__name__ in '__ERRORS__':
                        log(func.__name__ + " '__ERROR_CLASS_NAME__'")
                        raise '__ERROR_CLASS_NAME__'
                    log(func.__name__)
                return wrapper

            class Test(TestCase):
                @classmethod
                @log_call_and_maybe_error
                def setUpClass(cls):
                    cls.addClassCleanup(cls.classCleanup)

                @classmethod
                @log_call_and_maybe_error
                def classCleanup(cls):
                    pass

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

        pytester = fixture("pytester")()
        pytester.makepyfile(
            test_py
            .replace("'__ERRORS__'", repr(self.errors))
            .replace("'__ERROR_CLASS_NAME__'", self.error_class.__name__)
        )

        assert not log
        os.environ['TestClassCleanupPlugin_data'] = '[]'
        # fragile! other pytest plugins could break this
        result = pytester.runpytest('-qs', '-pno:django', '-pno:corehq', '-pno:warnings')
        result.assert_outcomes(**kwargs)
        # sharing via os.environ works because runpytest runs in the same process
        self.call_log = log[:]
        del log[:]

    def run_with_errors(self, *errors, error_class=Exception, **kwargs):
        if not kwargs:
            kwargs = {"failed": 1}
        self.errors = errors
        self.error_class = error_class
        self.run_suite(**kwargs)

    def test_cleanup_in_happy_path(self):
        self.run_with_errors(passed=1)
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown",
            "tearDownClass",
            "classCleanup",
        ])

    def test_cleanup_on_error_in_set_up_class(self):
        self.run_with_errors("setUpClass", errors=1)
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
        self.run_with_errors("tearDownClass", passed=1, errors=1)
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown",
            "tearDownClass Exception",
            "classCleanup",
        ])

    def test_cleanup_on_error_in_tearDown_and_tearDownClass(self):
        self.run_with_errors("tearDown", "tearDownClass", failed=1, errors=1)
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown Exception",
            "tearDownClass Exception",
            "classCleanup",
        ])

    def test_error_in_classCleanup(self):
        self.run_with_errors("classCleanup", passed=1, errors=1)
        eq(self.call_log, [
            "setUpClass",
            "setUp",
            "runTest",
            "tearDown",
            "tearDownClass",
            "classCleanup Exception",
        ])


def get_source(func):
    src = inspect.getsource(func)
    while True:
        firstline, src = src.split("\n", 1)
        if f'def {func.__name__}(' in firstline:
            return src
        assert src
