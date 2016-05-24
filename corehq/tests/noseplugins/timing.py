"""A test timing plugin for nose

Usage: ./manage.py test --with-timing --timing-file=/path/to/timing.csv
"""
import csv
import sys
import time

from nose.plugins import Plugin


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

    def configure(self, options, conf):
        """Configure plugin.
        """
        super(TimingPlugin, self).configure(options, conf)
        self.conf = conf
        self.timing_file = options.timing_file

    def begin(self):
        self.output = (open(self.timing_file, "w")
                       if self.timing_file else sys.__stdout__)
        self.csv = csv.writer(self.output)
        self.csv.writerow(["event name", "start time", "elapsed time"])
        self.event_start = time.time()

    def finalize(self, result):
        if self.output is not None:
            self.output.close()

    def end_event(self, name):
        now = time.time()
        self.csv.writerow([name, self.event_start, now - self.event_start])
        self.event_start = now

    def startContext(self, context):
        # called before context setup
        self.end_event("before {}".format(context))

    def startTest(self, case):
        # called before test is started
        self.end_event("setup {}".format(case.test))

    def stopTest(self, case):
        # called on test completion
        self.end_event("run {}".format(case.test))

    def stopContext(self, context):
        # called after context teardown
        self.end_event("teardown {}".format(context))
