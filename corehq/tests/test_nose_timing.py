import gc
import time
from tempfile import NamedTemporaryFile
from unittest import TestCase

from nose.plugins import PluginTester
from testil import Regex, eq

from corehq.util.test_utils import timelimit

from .noseplugins import timing as mod


class TimingPluginTesterBase(PluginTester, TestCase):
    activate = "--with-timing"
    plugins = [mod.TimingPlugin()]

    def setUp(self):
        with NamedTemporaryFile("w+", encoding="utf-8") as fh:
            self.args = [
                "--timing-file", fh.name,
                "--pretty-timing",
                "--max-test-time=0.05",
                "-v",
            ]
            gc.disable()
            try:
                # time-critical tests are run in here
                super().setUp()
            finally:
                gc.enable()
            fh.seek(0)
            print("---- begin test output ----")
            print(self.output)
            print("---- end test output ----")
            print("---- begin timing output ----")
            print(fh.read())
            print("---- end timing output ----")

    def print(self, *args):
        print(*args, file=mod.PLUGIN_INSTANCE.output)

    @property
    def ChattyTestBase(self):
        class ChattyTestBase(TestCase):
            @classmethod
            def setUpClass(cls):
                print("setUpClass")
                super().setUpClass()

            @classmethod
            def tearDownClass(cls):
                print("tearDownClass")
                super().tearDownClass()

            def setUp(self):
                print("setUp")
                super().setUp()

            def tearDown(self):
                print("tearDown")
                super().tearDown()

            def runTest(self):
                print("runTest")

        print = self.print
        ChattyTestBase.print = self.print
        return ChattyTestBase


class TestDefaultMaxSetupTime(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            @classmethod
            def setUpClass(cls):
                super().setUpClass()
                time.sleep(0.051)

            def setUp(self):
                # NOTE setUp() is part of "run" phase, not "setup"
                assert False, "should not get here"

        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"setup time limit \(0\.05\) exceeded: 0\.0[5-9]"))


class TestDefaultMaxTeardownTime(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            # NOTE tearDown() is part of "run" phase, not "teardown"
            @classmethod
            def tearDownClass(cls):
                super().tearDownClass()
                time.sleep(0.051)
        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"teardown time limit \(0\.05\) exceeded: 0\.0[5-9]"))


class TestDefaultMaxTestTime(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            def runTest(self):
                super().runTest()
                time.sleep(0.051)
        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.05\) exceeded: 0\.0[5-9]"))


class TestSetupExceedsMaxWithTestLimit(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            def setUp(self):
                super().setUp()
                time.sleep(0.051)

            @timelimit(0.001)
            def runTest(self):
                super().runTest()

        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.05\) exceeded: 0\.0[5-9]"))


class TestTeardownExceedsSumOfOtherLimits(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            @timelimit(0.001)
            def setUp(self):
                super().setUp()

            @timelimit(0.051)
            def runTest1(self):
                super().runTest()

            @timelimit(0.06)
            def runTest2(self):
                super().runTest()

            def tearDown(self):
                super().tearDown()
                time.sleep(0.0611)

        return [Test("runTest1"), Test("runTest2")]

    def test_time_limit1(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.052\) exceeded: 0\.0[6-9]"))

    def test_time_limit2(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.061\) exceeded: 0\.0[6-9]"))


class TestTimeLimitReset(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            @timelimit(0.051)
            def runTest1(self):
                super().runTest()
                time.sleep(0.052)

            def runTest2(self):
                super().runTest()
                time.sleep(0.052)

        return [Test("runTest1"), Test("runTest2")]

    def test_time_limit1(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.051\) exceeded: 0\.0[5-9]"))

    def test_time_limit2(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.05\) exceeded: 0\.0[5-9]"))


class TestExtendedTimeLimit(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            @timelimit(0.06)
            def runTest(self):
                super().runTest()
                time.sleep(0.061)
        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"runTest took too long: 0:00:00.0[6-9]"))


class TestPatchMaxTestTime(TimingPluginTesterBase):

    def makeSuite(self):
        @mod.patch_max_test_time(0.051)
        class Test(self.ChattyTestBase):
            @timelimit(0.001)
            def test1(self):
                super().runTest()
                time.sleep(0.01)

            def test2(self):
                super().runTest()
                time.sleep(0.052)

            @classmethod
            def tearDownClass(cls):
                super().tearDownClass()
                time.sleep(0.052)

        return [Test("test1"), Test("test2")]

    def test_time_limit_errors(self):
        output = str(self.output)
        eq(output, Regex(r"test1 took too long: 0:00:00\.0[1-9]"))
        eq(output, Regex(r"run time limit \(0\.051\) exceeded: 0\.0[5-9]"))

        # NOTE tearDownClass is not limited by class patch
        eq(output, Regex(r"teardown time limit \(0\.05\) exceeded: 0\.0[5-9]"))
