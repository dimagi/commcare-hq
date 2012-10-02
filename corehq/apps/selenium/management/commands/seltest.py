from django.core.management.commands import test
from south.management.commands import patch_for_test_db_setup
from testrunner import HqTestSuiteRunner
from pyvirtualdisplay import Display
from django.conf import settings
import sys

SELENIUM_TEST_MODULE = 'tests.selenium'

class TestSuiteRunner(HqTestSuiteRunner):

    def build_suite(self, test_labels, *args, **kwargs):
        import django.test.simple
        orig_test_module = django.test.simple.TEST_MODULE
        django.test.simple.TEST_MODULE = SELENIUM_TEST_MODULE

        try:
            return super(TestSuiteRunner, self).build_suite(test_labels,
                                                            *args, **kwargs)
        finally:
            django.test.simple.TEST_MODULE = orig_test_module


class Command(test.Command):
    help = 'Runs the selenium test suite for the specified applications, or the entire site if no apps are specified.'
    args = '[appname ...]'

    def handle(self, *test_labels, **options):
        verbosity = int(options.get('verbosity', 1))
        interactive = options.get('interactive', True)
        failfast = options.get('failfast', False)

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

        failures = test_runner.run_tests(test_labels)

        if failures:
            sys.exit(bool(failures))
