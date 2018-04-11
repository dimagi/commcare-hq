from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import SimpleTestCase
from corehq.apps.indicators.models import CouchIndicatorDef
from dimagi.utils.dates import DateSpan
from dateutil.parser import parse


class CouchIndicatorDefTests(SimpleTestCase):

    def _test_datespan_shifts(self, expected_start, months=0, days=0):
        idef = CouchIndicatorDef(
            fixed_datespan_months=months,
            fixed_datespan_days=days,
        )
        dspan = DateSpan(startdate=parse('2014-09-15T10:00:00'), enddate=parse('2014-09-30T11:00:00'))
        dspan = idef._apply_datespan_shifts(dspan)
        self.assertEqual(dspan.enddate, parse('2014-09-30T23:59:59.999999'))
        self.assertEqual(dspan.startdate, parse(expected_start))

    def test_fixed_datespan_months_1(self):
        self._test_datespan_shifts('2014-09-01T00:00:00', months=1)

    def test_fixed_datespan_months_3(self):
        self._test_datespan_shifts('2014-07-01T00:00:00', months=3)

    def test_fixed_datespan_days_1(self):
        self._test_datespan_shifts('2014-09-30T00:00:00', days=1)

    def test_fixed_datespan_days_7(self):
        self._test_datespan_shifts('2014-09-24T00:00:00', days=7)
