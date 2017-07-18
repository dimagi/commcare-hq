"""Print collected test output for passing tests

Usage: ./manage.py test --with-output
"""
from nose.plugins import Plugin
from nose.plugins.capture import Capture
from nose.plugins.logcapture import LogCapture

from corehq.tests.noseplugins.uniformresult import uniform_description


class OutputPlugin(Plugin):
    """Print collected test output for passing tests"""

    name = "output"

    def configure(self, options, conf):
        super(OutputPlugin, self).configure(options, conf)
        if self.enabled:
            self.output = []
            # monkey-patch plugins to grab captured output
            Capture.addSuccess = addSuccess
            LogCapture.addSuccess = addSuccess

    def startTest(self, case):
        case.__output = []

    def stopTest(self, case):
        if case.__output:
            name = uniform_description(case.test)
            self.output.extend(["=" * 70, "PASS: " + name])
            self.output.extend(case.__output)

    def report(self, stream):
        for line in self.output:
            stream.writeln(line)


def addSuccess(self, test):
    err = (None, None, None)
    output = self.formatError(test, err)
    if output is not err:
        output = output[1].split('\n', 1)[1]
        test._OutputPlugin__output.append(output)
