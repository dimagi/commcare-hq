"""A test timing plugin for nose

Usage: ./manage.py test --with-timing --timing-file=/path/to/timing.csv
"""
import csv
import sys
import time

from nose.plugins import Plugin
from corehq.tests.noseplugins.uniformresult import uniform_description


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

    def configure(self, options, conf):
        """Configure plugin.
        """
        super(TimingPlugin, self).configure(options, conf)
        self.conf = conf
        self.timing_file = options.timing_file
        self.pretty_output = options.pretty_output
        self.threshold = options.threshold

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

    def startContext(self, context):
        # called before context setup
        self.end_event("before", context)

    def startTest(self, case):
        # called before test is started
        self.end_event("setup", case.test)

        import cProfile
        self.profile = cProfile.Profile()
        self.profile.enable()
        self.profile_start = time.time()

    def stopTest(self, case):
        # called on test completion
        self.profile.disable()
        self.end_event("run", case.test)

        if time.time() - self.profile_start > 100:
            self.print_stats(self.profile)
            assert 0, "fail for early travis results"
        self.profile = None

    def stopContext(self, context):
        # called after context teardown
        self.end_event("teardown", context)

    def print_stats(self, profile):
        import pstats
        import subprocess
        stats = pstats.Stats(profile, stream=sys.stderr).sort_stats('cumulative')
        stats.print_stats()
        # also get kafka logs since there is suspicion of problems there
        out = subprocess.check_output(['docker', 'logs', 'hqtest_kafka_1']).decode('utf8')
        sys.stderr.write(f'{out}\n')
        sys.stderr.flush()


PLUGIN_INSTANCE = None


def end_event(name, context):
    """Signal the end of a custom timing event

    Use to add arbitrary "events" anywhere in the code to isolate
    sources of slowness during profiling. This function terminates the
    given event name and immediately begins the next (as yet unnamed)
    event. Requires the `TimingPlugin` must to be enabled.
    """
    PLUGIN_INSTANCE.end_event(name, context)
