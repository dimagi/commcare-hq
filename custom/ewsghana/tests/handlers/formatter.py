from django.test.testcases import SimpleTestCase
from custom.ewsghana.handlers.alerts import EWSFormatter


class TestFormatter(SimpleTestCase):

    def test_parser1(self):
        self.assertEqual(EWSFormatter().format('lf10.0mc20.0'), 'lf 10.0 mc 20.0')
        self.assertEqual(EWSFormatter().format('LF10.0MC 20.0'), 'lf 10.0 mc 20.0')
        self.assertEqual(EWSFormatter().format('LF10-1MC 20,3'), 'lf 10.1 mc 20.3')
        self.assertEqual(EWSFormatter().format('LF(10.0), mc (20.0)'), 'lf 10.0 mc 20.0')
        self.assertEqual(EWSFormatter().format('LF10.0-mc20.0'), 'lf 10.0 mc 20.0')
        self.assertEqual(EWSFormatter().format('LF10.0-mc20- 0'), 'lf 10.0 mc 20.0')
        self.assertEqual(EWSFormatter().format('LF10-3mc20 0'), 'lf 10.3 mc 20.0')
        self.assertEqual(EWSFormatter().format('LF10----3mc20.0'), 'lf 10.3 mc 20.0')


