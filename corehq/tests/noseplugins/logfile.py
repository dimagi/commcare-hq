"""A plugin to log test failures to a file

This is useful to preserve error output from a test run in a file in
additon to displaying the output in a terminal. It is also possible to
to view errors (in the log file) as soon as they occur while running
very large test suites.

The log file will not be overwritten if the test run completes with no
errors or failures.

Usage:

    ./manage.py test --log-file=test-failures.log
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import os
import sys
from io import open
try:
    from shlex import quote  # py3
except ImportError:
    from pipes import quote  # py2
from unittest.runner import TextTestResult, _WritelnDecorator
from nose.plugins import Plugin

import six


class LogFilePlugin(Plugin):
    """Log test failures to file"""

    name = "log-file"

    def options(self, parser, env):
        # Do not call super to avoid adding a ``--with`` option for this plugin
        parser.add_option('--log-file',
                          default=env.get('NOSE_LOG_FILE'),
                          help="File in which to log test failures. "
                               "[NOSE_LOG_FILE]")

    def configure(self, options, conf):
        if options.log_file:
            self.enabled = True
            self.log_path = os.path.expanduser(options.log_file)
            self.log_file = None
            self.argv = sys.argv
            self.start = datetime.datetime.now()

    def setup_log(self):
        mode = "w" if six.PY3 else "wb"
        self.log_file = _WritelnDecorator(open(self.log_path, mode))
        self.log_file.writeln(" ".join(quote(a) for a in self.argv))
        self.log_file.writeln(str(self.start))
        self.result = TextTestResult(self.log_file, True, 0)

    def log(self, label, test, err):
        if self.log_file is None:
            self.setup_log()
        if isinstance(err[1], six.text_type):
            value = type(err[0].__name__, (Exception,), {})(err[1])
            err = (err[0], value, err[2])
        err_string = self.result._exc_info_to_string(err, test)
        self.result.printErrorList(label, [(test, err_string)])
        self.log_file.flush()

    def addError(self, test, err):
        self.log("ERROR", test, err)

    def addFailure(self, test, err):
        self.log("FAIL", test, err)

    def finalize(self, result):
        if self.log_file is not None:
            self.log_file.writeln(str(datetime.datetime.now()))
            self.log_file.close()
