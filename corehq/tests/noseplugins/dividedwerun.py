import logging
import types
from hashlib import md5
from unittest import SkipTest

from nose.case import Test, FunctionTestCase
from nose.failure import Failure
from nose.plugins import Plugin
from nose.suite import ContextSuite
from nose.tools import nottest


log = logging.getLogger(__name__)


class DividedWeRunPlugin(Plugin):
    """Run a predictably random subset of tests

    Warning: this plugin is not compatible with other plugins that return
    something other than a `ContextSuite` from `prepareTest`.
    """

    name = "divided-we-run"

    def options(self, parser, env):
        # Do not call super to avoid adding a ``--with`` option for this plugin
        parser.add_option('--divided-we-run',
                          default=env.get('NOSE_DIVIDED_WE_RUN'),
                          help="Run a predictably random subset of tests based "
                               "on test name. The value of this option should "
                               "be one or two hexadecimal digits denoting the "
                               "first and last bucket to include, where each "
                               "bucket is a predictably random hex digit based "
                               "on the test (module) path. "
                               "[NOSE_DIVIDED_WE_RUN]")
        parser.add_option('--divide-depth',
                          default=env.get('NOSE_DIVIDE_DEPTH', '0'),
                          help="Number of suite contexts to descend into when "
                               "dividing tests. [NOSE_DIVIDE_DEPTH]")

    def configure(self, options, conf):
        if options.divided_we_run:
            self.enabled = True
            if len(options.divided_we_run) not in [1, 2]:
                raise ValueError("invalid divided-we-run value: "
                                 "expected 1 or 2 hexadecimal digits")
            self.divided_we_run = options.divided_we_run
            self.first_bucket = options.divided_we_run[0]
            self.last_bucket = options.divided_we_run[-1]
            self.divide_depth = int(options.divide_depth)
            if int(self.first_bucket, 16) > int(self.last_bucket, 16):
                raise ValueError(
                    "divided-we-run range start is after range end")

    def prepareTest(self, test):
        return self.skip_out_of_range_tests(test)

    def skip_out_of_range_tests(self, test, depth=0):
        if isinstance(test, ContextSuite):
            if depth >= self.divide_depth:
                return self.maybe_skip(test)
            depth += 1 if test.implementsAnyFixture(test.context, None) else 0
            test._tests = [self.skip_out_of_range_tests(case, depth)
                           for case in test]
        else:
            test = self.maybe_skip(test)
        return test

    def maybe_skip(self, test):
        bucket = get_score(test)
        log.debug("%s divided-we-run=%s bucket=%s",
                  name_of(test), self.divided_we_run, bucket)
        if bucket < self.first_bucket or bucket > self.last_bucket:
            def skip():
                raise SkipTest("divided-we-run: {} not in range {}".format(
                               bucket, self.divided_we_run))
            if isinstance(test, ContextSuite):
                desc = get_descriptor(test)
            elif isinstance(test.test, Failure):
                return get_descriptive_failing_test(test.test)
            elif test.test.descriptor is None:
                desc = get_descriptor(test)
            else:
                desc = test.test.descriptor
            return Test(
                FunctionTestCase(skip, descriptor=desc),
                getattr(test, 'config', None),
                getattr(test, 'resultProxy', None),
            )
        return test


def name_of(test):
    """Returns the full name of the test as a string."""
    if not isinstance(test, ContextSuite):
        return str(test)
    context = test.context
    if isinstance(context, type) or isinstance(context, types.FunctionType):
        return context.__module__ + ":" + context.__name__
    if isinstance(context, types.ModuleType):
        return context.__name__
    return str(context)


def get_score(test):
    """Returns the score for a test, which is derived from the MD5 hex digest
    of the test's (possibly truncated) name.

    Calls ``name_of(test)`` to acquire the "full name", then truncates that
    value at the first occurrence of an open-parenthesis character (or the
    entire name if none exist) before generating the MD5 digest.

    Example:

    .. code-block:: python

        >>> name_of(test_this)
        'module.test_func(<This at 0xffffaaaaaaaa>)'
        >>> name_of(test_other)
        'module.test_func(<Other at 0xffffeeeeeeee>)'
        >>> md5(name_of(test_this)).hexdigest()
        '45fd9a647841b1e65633f332ee5f759b'
        >>> md5(name_of(test_other)).hexdigest()
        'acf7e690fb7d940bfefec1d06392ee17'
        >>> get_score(test_this)
        'c'
        >>> get_score(test_other)
        'c'
    """
    runtime_safe = name_of(test).split("(", 1)[0]
    return md5(runtime_safe.encode('utf-8')).hexdigest()[0]


def get_descriptor(test):
    def descriptor():
        raise Exception("unexpected call")
    if hasattr(test.context, "__module__"):
        return test.context
    name = test.context.__name__
    if "." in name:
        name, descriptor.__name__ = name.rsplit(".", 1)
    else:
        descriptor.__name__ = "*"
    descriptor.__module__ = name
    return descriptor


@nottest
def get_descriptive_failing_test(failure_obj):
    """Get descriptive test from failure object

    Useful for extracting descriptive details from a test failure that
    occurs during test collection. This can happen when test generator
    function raises an exception such as SkipTest, for example.
    """
    def fail():
        raise failure_obj.exc_val
    tb = failure_obj.tb
    while tb.tb_next is not None:
        tb = tb.tb_next
    frame = tb.tb_frame
    try:
        descriptor = frame.f_globals[frame.f_code.co_name]
    except KeyError:
        def descriptor():
            raise Exception("unexpected call")
        descriptor.__name__ = str(frame)
    return Test(
        FunctionTestCase(fail, descriptor=descriptor),
        getattr(failure_obj, 'config', None),
        getattr(failure_obj, 'resultProxy', None),
    )
