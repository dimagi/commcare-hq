"""A temporary plugin for debugging tests

This is useful for finding tests that do not cleanup after themselves.

Usage:

- Uncomment 'corehq.tests.noseplugins.debug.DebugPlugin' in testsettings.py
- Customize DebugPlugin below to inspect state.

Tips:

- Write to `sys.__stdout__` to bypass stdout and logging collector.
- `afterContext` is run at test collection time, not after teardown.
- Plugin interface:
    https://nose.readthedocs.org/en/latest/plugins/interface.html
"""
from __future__ import absolute_import
import sys
from nose.plugins import Plugin


class DebugPlugin(Plugin):
    """Temporary debugging plugin"""

    name = "debug"
    enabled = True

    def options(self, parser, env):
        """Avoid adding a ``--with`` option for this plugin."""

    def configure(self, options, conf):
        """Do not call super (always enabled)"""

#    def prepareTestCase(self, case):
#        from custom.ewsghana.models import FacilityInCharge
#        def audit(result):
#            try:
#                case.test(result)
#            finally:
#                sys.__stdout__.write("{}: {}\n".format(
#                    case.test,
#                    [f.id for f in FacilityInCharge.objects.all()],
#                ))
#        return audit

    def stopContext(self, context):
        from django.contrib.auth.models import User
        num = User.objects.filter(username='user1').count()
        if num:
            sys.__stdout__.write("\n{} {}\n".format(num, context))

#    def wantFunction(self, func):
#        """Do not want 'test' functions with required args"""
#        import inspect
#        if "test" in func.__name__ and getattr(func, '__test__', True):
#            spec = inspect.getargspec(func)
#            return len(spec.args) <= len(spec.defaults or [])
#        return None
