from django.core.management.commands import test
from south.management.commands import patch_for_test_db_setup
from testrunner import HqTestSuiteRunner
from selenium import webdriver
from pyvirtualdisplay import Display
from django.conf import settings
import sys

SELENIUM_TEST_MODULE = 'tests.selenium'


class TestSuiteRunner(HqTestSuiteRunner):

    def build_suite(self, test_labels, *args, **kwargs):
        """
        Override the default test suite builder to use 'tests.selenium' as the
        test module path, allow excluding the tests of any apps contained in
        settings.SELENIUM_EXCLUDE_APPS, and exclude doctests.

        """
        from django.test.simple import (unittest, build_test, get_app,
                get_apps, reorder_suite, TestCase, doctest,
                build_suite as _build_suite)

        # Hack to remove doctests from test suite without reimplementing
        # build_suite
        def _filter_suite(suite):
            tests = []
            for test in suite._tests:
                if isinstance(test, unittest.TestSuite):
                    tests.append(_filter_suite(test))
                elif not isinstance(test, doctest.DocTestCase):
                    tests.append(test)

            suite._tests = tests
            return suite

        def build_suite(*args, **kwargs):
            suite = _build_suite(*args, **kwargs)
            return _filter_suite(suite)

        exclude_apps = getattr(settings, 'SELENIUM_EXCLUDE_APPS', [])
        test_labels = [l for l in test_labels
                       if all(not l.startswith(app) for app in exclude_apps)]

        import django.test.simple
        orig_test_module = django.test.simple.TEST_MODULE
        django.test.simple.TEST_MODULE = SELENIUM_TEST_MODULE

        try:
            suite = unittest.TestSuite()

            if test_labels:
                for label in test_labels:
                    if '.' in label:
                        suite.addTest(build_test(label))
                    else:
                        app = get_app(label)
                        suite.addTest(build_suite(app))
            else:
                for app in get_apps():
                    name = app.__name__
                    if all(('.%s' % a) not in name for a in exclude_apps):
                        suite.addTest(build_suite(app))

            return reorder_suite(suite, (TestCase,))

        finally:
            django.test.simple.TEST_MODULE = orig_test_module


class Command(test.Command):
    help = 'Runs the selenium test suite for the specified applications, or the entire site if no apps are specified.'
    args = '[appname ...]'

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        interactive = options.get('interactive', True)
        failfast = options.get('failfast', False)
        args = list(args)
        
        # Modify selenium settings in-place. Not the worst hack ever.
        if args and hasattr(webdriver, args[0].capitalize()):
            settings.SELENIUM_BROWSER = args.pop(0)
            if args and args[0].startswith('http'):
                settings.SELENIUM_BROWSER = 'Remote'
                settings.SELENIUM_REMOTE_URL = args.pop(0)

        # Apply south migrations, as South does in its test command that
        # replaces django's default test command
        patch_for_test_db_setup()

        if settings.SELENIUM_XVFB:
            print "starting X Virtual Framebuffer display"
            Display(backend='xvfb',
                    size=settings.SELENIUM_XVFB_DISPLAY_SIZE).start()

        test_runner = TestSuiteRunner(verbosity=verbosity,
                                      interactive=interactive,
                                      failfast=failfast)

        failures = test_runner.run_tests(args)

        if failures:
            sys.exit(bool(failures))
