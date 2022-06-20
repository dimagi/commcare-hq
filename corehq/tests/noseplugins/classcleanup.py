"""Call TestCase.doClassCleanups after each test"""
import sys
from traceback import print_exception

from nose.plugins import Plugin


class ClassCleanupPlugin(Plugin):
    """Call TestCase.doClassCleanups after running tests on a test class

    Nose overrides the part of the default Python test suite runner
    that normally calls TestCase.doClassCleanups(). This plugin ensures
    that it gets called.
    """

    name = "classcleanup"
    enabled = True

    def options(self, parser, env):
        """Do not call super (always enabled)"""

    def begin(self):
        self.patch_django_test_case()

    def handleError(self, test, err):
        if getattr(test, "error_context", None) in {"setup", "teardown"}:
            self._do_class_cleanups(test.context)

    def stopContext(self, context):
        self._do_class_cleanups(context)

    def _do_class_cleanups(self, context):
        cleanup = getattr(context, "doClassCleanups", None)
        if cleanup is not None:
            cleanup()
            errors = getattr(context, "tearDown_exceptions", None)
            if errors:
                if len(errors) > 1:
                    num = len(errors)
                    for n, (exc_type, exc, tb) in enumerate(errors[:-1], start=1):
                        print(f"\nclass cleanup error ({n} of {num}):", file=sys.stderr)
                        print_exception(exc_type, exc, tb)
                raise errors[-1][1]

    def patch_django_test_case(self):
        """Do class cleanups before TestCase transaction rollback"""
        from django.test import TestCase

        @classmethod
        def tearDownClass(cls):
            try:
                self._do_class_cleanups(cls)
            finally:
                real_tearDownClass(cls)

        real_tearDownClass = TestCase.tearDownClass.__func__
        TestCase.tearDownClass = tearDownClass
