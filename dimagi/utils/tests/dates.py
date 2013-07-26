from datetime import datetime
from dimagi.utils.dates import DateSpan
from django.test import TestCase

class DateSpanSinceTest(TestCase):
    def test_since(self):
        enddate = datetime(2013, 7, 21, 12, 30, 45)
        datespan_inclusive = DateSpan.since(7, enddate)
        self.assertEqual(datespan_inclusive.enddate, datetime(2013, 7, 21, 0, 0, 0))
        self.assertEqual(datespan_inclusive.startdate, datetime(2013, 7, 15, 0, 0, 0))

        datespan_non_inclusive = DateSpan.since(7, enddate, inclusive=False)
        self.assertEqual(datespan_non_inclusive.enddate, datetime(2013, 7, 21, 0, 0, 0))
        self.assertEqual(datespan_non_inclusive.startdate, datetime(2013, 7, 14, 0, 0, 0))
