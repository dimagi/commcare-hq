"""A test timing plugin for nose

Usage: ./manage.py test --with-timing --timing-file=/path/to/timing.csv
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import csv342 as csv
import sys
import time

from nose.plugins import Plugin
from corehq.tests.noseplugins.uniformresult import uniform_description
from io import open


class TimingPlugin(Plugin):
    """A plugin to measure times of testing events

    Measure elapsed time before setup, during setup, during test, and
    during teardown events. Outputs the results as CSV.
    """
    name = "timing"

    def options(self, parser, env):
        """Register commandline options.
        """
        super(TimingPlugin, self).options(parser, env)
        parser.add_option('--timing-file', action='store',
                          dest='timing_file',
                          metavar="FILE",
                          default=env.get('NOSE_TIMING_FILE'),
                          help='Timing output file (CSV); default is STDOUT')
        parser.add_option('--pretty-timing', action='store_true',
                          dest='pretty_output',
                          default=env.get('NOSE_PRETTY_TIMING'),
                          help='Print timing info in a format that is better '
                               'for reviewing in text mode (not CSV).')
        parser.add_option('--threshold', type=int,
                          default=env.get('NOSE_TIMING_THRESHOLD'),
                          help='Only print timing info for events above this threshold (seconds).')
        parser.add_option('--fail-slow-tests', action='store_true',
                          dest='fail_slow_tests',
                          help='Fails any tests that are over the threshold specified.')

    def configure(self, options, conf):
        """Configure plugin.
        """
        super(TimingPlugin, self).configure(options, conf)
        self.conf = conf
        self.timing_file = options.timing_file
        self.pretty_output = options.pretty_output
        self.threshold = options.threshold
        self.fail_slow_tests = options.fail_slow_tests

    def begin(self):
        self.output = (open(self.timing_file, "w", encoding='utf-8')
                       if self.timing_file else sys.__stdout__)
        if not self.pretty_output:
            self.csv = csv.writer(self.output)
            self.csv.writerow(["event", "name", "elapsed time", "start time"])
        self.event_start = time.time()
        global PLUGIN_INSTANCE
        PLUGIN_INSTANCE = self

    def finalize(self, result):
        if self.output is not None:
            self.output.close()

    def end_event(self, event, context):
        now = time.time()
        name = uniform_description(context)
        duration = now - self.event_start
        if self.threshold and duration < self.threshold:
            self.event_start = now
            return

        if self.pretty_output:
            self.output.write("{time:>-6,.2f}  {event} {name}\n".format(
                event=event,
                name=name,
                time=duration,
            ))
        else:
            self.csv.writerow([
                event,
                name,
                duration,
                self.event_start,
            ])
        self.event_start = now

        slow_seconds = _get_expected_slow_seconds(context) or self.threshold
        if self.fail_slow_tests and event != 'before' and duration > slow_seconds:
            context.fail("""
            Test ran in {} seconds and is greater than threshold {}.
            For tips on speeding up these tests please refer to https://commcare-hq.readthedocs.io/testing.html
            """.format(duration, slow_seconds))

    def startContext(self, context):
        # called before context setup
        self.end_event("before", context)

    def startTest(self, case):
        # called before test is started
        self.end_event("setup", case.test)

    def stopTest(self, case):
        # called on test completion
        self.end_event("run", case.test)

    def stopContext(self, context):
        # called after context teardown
        self.end_event("teardown", context)


PLUGIN_INSTANCE = None


def end_event(name, context):
    """Signal the end of a custom timing event

    Use to add arbitrary "events" anywhere in the code to isolate
    sources of slowness during profiling. This function terminates the
    given event name and immediately begins the next (as yet unnamed)
    event. Requires the `TimingPlugin` must to be enabled.
    """
    PLUGIN_INSTANCE.end_event(name, context)


def _get_expected_slow_seconds(test_context):
    # If we skip this test, but its slow due to other test setup
    fn = getattr(test_context, 'test', None)
    if fn and hasattr(fn, 'func_name') and fn.func_name == 'skip':
        return 1000

    # class is tagged for class based test
    slow_seconds = getattr(test_context, 'slow', None)

    # Function is tagged in a class based test
    if slow_seconds is None and hasattr(test_context, '_testMethodName'):
        fn = getattr(test_context, test_context._testMethodName)
        slow_seconds = getattr(fn, 'slow', None)

    # For function based test, the function is tagged
    if slow_seconds is None and hasattr(test_context, 'test'):
        fn = test_context.test
        slow_seconds = getattr(fn, 'slow', None)

    return slow_seconds
