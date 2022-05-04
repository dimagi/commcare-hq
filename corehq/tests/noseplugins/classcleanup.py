"""Call TestCase.doClassCleanups after each test"""
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

    def handleError(self, test, err):
        if getattr(test, "error_context", None) in {"setup", "teardown"}:
            self._do_class_cleanups(test.context)

    def stopContext(self, context):
        self._do_class_cleanups(context)

    def _do_class_cleanups(self, context):
        cleanup = getattr(context, "doClassCleanups", None)
        if cleanup is not None:
            cleanup()
