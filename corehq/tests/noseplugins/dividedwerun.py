import logging
import sys
import types
from hashlib import md5
from unittest import SkipTest

from nose.case import Test, FunctionTestCase
from nose.plugins import Plugin
from nose.suite import ContextSuite

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
            if depth > self.divide_depth \
                    and test.implementsAnyFixture(test.context, None):
                return self.maybe_skip(test)
            test._tests = [self.skip_out_of_range_tests(case, depth + 1)
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
            desc = test.context if isinstance(test, ContextSuite) else test.test
            return Test(
                FunctionTestCase(skip, descriptor=desc),
                getattr(test, 'config', None),
                getattr(test, 'resultProxy', None),
            )
        return test


def name_of(test):
    if not isinstance(test, ContextSuite):
        return str(test)
    context = test.context
    if isinstance(context, type) or isinstance(context, types.FunctionType):
        return context.__module__ + ":" + context.__name__
    if isinstance(context, types.ModuleType):
        return context.__name__
    raise str(context)


def get_score(test):
    return md5(name_of(test)).hexdigest()[0]
