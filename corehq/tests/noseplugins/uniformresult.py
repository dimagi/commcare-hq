"""A plugin to format test names uniformly for easy comparison

Usage:

    # collect django tests
    COLLECT_ONLY=1 ./manage.py test -v2 --settings=settings 2> tests-django.txt

    # collect nose tests
    ./manage.py test -v2 --collect-only --with-uniform-results 2> tests-nose.txt

    # clean up django test output: s/skipped\ \'.*\'$/ok/
    # sort each output file
    # diff tests-django.txt tests-nose.txt
"""
from types import ModuleType

from nose.case import FunctionTestCase
from nose.plugins import Plugin


def uniform_description(test):
    if type(test).__name__ == "DocTestCase":
        return test._dt_test.name
    if isinstance(test, ModuleType):
        return test.__name__
    if isinstance(test, type):
        return "%s:%s" % (test.__module__, test.__name__)
    if isinstance(test, FunctionTestCase):
        return str(test)
    name = "%s:%s.%s" % (
        test.__module__,
        type(test).__name__,
        test._testMethodName
    )
    return name
    #return sys.modules[test.__module__].__file__


class UniformTestResultPlugin(Plugin):
    """Format test descriptions for easy comparison
    """

    name = "uniform-results"

    def describeTest(self, test):
        return uniform_description(test.test)
