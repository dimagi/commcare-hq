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
                "--max-test-time=0.01",
                "-v",
            ]
            super().setUp()
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
                time.sleep(0.011)

            def setUp(self):
                # NOTE setUp() is part of "run" phase, not "setup"
                assert False, "should not get here"

        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"setup time limit \(0\.01\) exceeded: 0\.01\d"))


class TestDefaultMaxTeardownTime(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            # NOTE tearDown() is part of "run" phase, not "teardown"
            @classmethod
            def tearDownClass(cls):
                super().tearDownClass()
                time.sleep(0.011)
        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"teardown time limit \(0\.01\) exceeded: 0\.0[1-9]"))


class TestDefaultMaxTestTime(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            def runTest(self):
                super().runTest()
                time.sleep(0.011)
        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.01\) exceeded: 0\.0[1-9]"))


class TestSetupExceedsMaxWithTestLimit(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            def setUp(self):
                super().setUp()
                time.sleep(0.011)

            @timelimit(0.001)
            def runTest(self):
                super().runTest()

        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.01\) exceeded: 0\.0[1-9]"))


class TestTeardownExceedsSumOfOtherLimits(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            @timelimit(0.001)
            def setUp(self):
                super().setUp()

            @timelimit(0.01)
            def runTest1(self):
                super().runTest()

            @timelimit(0.02)
            def runTest2(self):
                super().runTest()

            def tearDown(self):
                super().tearDown()
                time.sleep(0.0211)

        return [Test("runTest1"), Test("runTest2")]

    def test_time_limit1(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.011\) exceeded: 0\.0[1-9]"))

    def test_time_limit2(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.021\) exceeded: 0\.0[2-9]"))


class TestTimeLimitReset(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            @timelimit(0.011)
            def runTest1(self):
                super().runTest()
                time.sleep(0.012)

            def runTest2(self):
                super().runTest()
                time.sleep(0.012)

        return [Test("runTest1"), Test("runTest2")]

    def test_time_limit1(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.011\) exceeded: 0\.0[1-9]"))

    def test_time_limit2(self):
        output = str(self.output)
        eq(output, Regex(r"run time limit \(0\.01\) exceeded: 0\.0[1-9]"))


class TestExtendedTimeLimit(TimingPluginTesterBase):

    def makeSuite(self):
        class Test(self.ChattyTestBase):
            @timelimit(0.02)
            def runTest(self):
                super().runTest()
                time.sleep(0.021)
        return [Test()]

    def test_time_limit(self):
        output = str(self.output)
        eq(output, Regex(r"runTest took too long: 0:00:00.02"))
