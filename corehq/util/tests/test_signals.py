from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.signals import SignalHandlerContext
import os
import signal
from unittest import TestCase


class SignalsTests(TestCase):
    def tearDown(self):
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    def test_signals_do_something(self):
        test_data = {}

        def signal_handler(signal, frame):
            test_data["floppy ears"] = True

        with SignalHandlerContext([signal.SIGINT], signal_handler):
            os.kill(os.getpid(), signal.SIGINT)

        self.assertTrue(test_data["floppy ears"])

    def test_returns_to_default(self):
        test_data = {}

        def signal_handler(signal, frame):
            test_data["whiskers"] = True

        with SignalHandlerContext(signal.SIGINT, signal_handler, signal.SIG_IGN):
            pass

        os.kill(os.getpid(), signal.SIGINT)

        self.assertNotIn("whiskers", test_data)
