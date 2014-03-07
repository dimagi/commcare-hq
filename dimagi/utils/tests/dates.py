from datetime import datetime, timedelta
import pytz
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


class DateSpanTimezoneTest(TestCase):

    def test_defaults(self):
        end = datetime.utcnow()
        start = end - timedelta(days=7)
        ds = DateSpan(start, end)
        self.assertEqual(ds.timezone, pytz.utc)

    def test_adjustment(self):
        end = datetime(2014, 3, 7, 2, tzinfo=pytz.utc)
        start = end = datetime(2014, 2, 7, 2, tzinfo=pytz.utc)
        ds = DateSpan(start, end)
        pst = pytz.timezone('US/Pacific-New')
        ds.set_timezone(pst)
        self.assertEqual(ds.enddate - end, timedelta(hours=8))
        self.assertEqual(ds.startdate - start, timedelta(hours=8))
        self.assertEqual(ds.timezone, pst)
