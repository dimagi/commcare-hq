import gc
import inspect

from testil import Regex
from unmagic import fixture

pytest_plugins = ["pytester"]


class TimeLimitTestCase:

    def setup_method(self):
        pytester = fixture("pytester")()
        self.create_pytester_files(pytester)
        plugin_opts = [
            "-pno:django",
            "-pno:corehq",
            "-pcorehq.tests.pytest_plugins.timelimit"
        ]
        gc.disable()
        try:
            # time-critical tests are run in here
            result = pytester.runpytest(*plugin_opts, "-lv", "--max-test-time=0.05")
        finally:
            gc.enable()
        self.output = str(result.stdout)

    def create_pytester_files(self, pytester):
        pytester.makepyfile(get_source(self.pyfile_code))


class TestDefaultMaxSetupTime(TimeLimitTestCase):

    def pyfile_code(self):
        import time
        from unittest import TestCase

        class Test(TestCase):
            @classmethod
            def setUpClass(cls):
                super().setUpClass()
                time.sleep(0.051)

            def setUp(self):
                # NOTE setUp() is part of "runtest", not "setup" event
                assert False, "should not get here"

            test = setUp

            @classmethod
            def tearDownClass(cls):
                assert 0, 'tearDownClass was called'

    def test_time_limit(self):
        assert self.output == Regex(r"setup time limit \(0\.05\) exceeded: 0\.0[5-9]")

    def test_teardownclass_called_if_setupclass_limit_exceeded(self):
        assert "tearDownClass was called" in self.output

    def test_setUp_not_called(self):
        assert "should not get here" not in self.output


class TestDefaultMaxTeardownTime(TimeLimitTestCase):

    def pyfile_code(self):
        import time
        from unittest import TestCase

        class Test(TestCase):
            # NOTE tearDown() is part of "runtest", not "teardown" event
            @classmethod
            def tearDownClass(cls):
                time.sleep(0.051)

            def test(self):
                pass

    def test_time_limit(self):
        assert self.output == Regex(r"teardown time limit \(0\.05\) exceeded: 0\.0[5-9]")


class TestDefaultMaxTestTime(TimeLimitTestCase):

    def pyfile_code(self):
        import time
        from unittest import TestCase

        class Test(TestCase):
            def runTest(self):
                time.sleep(0.051)

    def test_time_limit(self):
        assert self.output == Regex(r"test time limit \(0\.05\) exceeded: 0\.0[5-9]")


class TestSetupExceedsMaxTestTimeLimit(TimeLimitTestCase):

    def pyfile_code(self):
        import time
        from unittest import TestCase
        from corehq.util.test_utils import timelimit

        class Test(TestCase):
            def setUp(self):
                time.sleep(0.051)

            @timelimit(0.001)
            def test(self):
                pass

    def test_time_limit(self):
        assert self.output == Regex(r"test time limit \(0\.05\) exceeded: 0\.0[5-9]")


class TestTeardownExceedsMaxTestTimeLimit(TimeLimitTestCase):

    def pyfile_code(self):
        import time
        from unittest import TestCase
        from corehq.util.test_utils import timelimit

        class Test(TestCase):
            @timelimit(0.021)
            def setUp(self):
                pass

            @timelimit(0.041)
            def test(self):
                pass

            def tearDown(self):
                time.sleep(0.063)

    def test_time_limit(self):
        assert self.output == Regex(r"test time limit \(0\.062\) exceeded: 0\.0[6-9]")


class TestTimeLimitReset(TimeLimitTestCase):

    def pyfile_code(self):
        import time
        from unittest import TestCase
        from corehq.util.test_utils import timelimit

        class Test(TestCase):
            @timelimit(0.051)
            def test_1(self):
                time.sleep(0.052)

            def test_2(self):
                time.sleep(0.052)

    def test_time_limit1(self):
        assert self.output == Regex(r"test_1 time limit \(0\.051\) exceeded: 0\.0[5-9]")

    def test_time_limit2(self):
        assert self.output == Regex(r"test time limit \(0\.05\) exceeded: 0\.0[5-9]")


class TestOverrideTimeLimit(TimeLimitTestCase):

    def pyfile_code(self):
        import time
        from unittest import TestCase
        from corehq.util.test_utils import timelimit

        class Test(TestCase):
            @timelimit(0.06)
            def test(self):
                time.sleep(0.051)

    def test_time_limit(self):
        assert "exceeded" not in self.output


class TestNestedTimeLimits(TimeLimitTestCase):

    def pyfile_code(self):
        from time import sleep
        from corehq.tests.util.timelimit import timelimit

        @timelimit(0.05)
        def slowdown():
            sleep(0.02)

        @timelimit(0.05)
        def test_nested_timelimit():
            slowdown()
            sleep(0.04)

    def test_time_limit(self):
        assert "exceeded" not in self.output


def get_source(method):
    src = inspect.getsource(method)
    firstline, body = src.split("\n", 1)
    assert f'def {method.__name__}(' in firstline, src
    return body
