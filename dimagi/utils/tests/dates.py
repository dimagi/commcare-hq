from datetime import datetime, timedelta, date
import pytz
from dimagi.utils.dates import DateSpan, add_months_to_date
from django.test import SimpleTestCase

class DateSpanSinceTest(SimpleTestCase):
    def test_since(self):
        enddate = datetime(2013, 7, 21, 12, 30, 45)
        datespan_inclusive = DateSpan.since(7, enddate)
        self.assertEqual(datespan_inclusive.enddate, datetime(2013, 7, 21, 0, 0, 0))
        self.assertEqual(datespan_inclusive.startdate, datetime(2013, 7, 15, 0, 0, 0))

        datespan_non_inclusive = DateSpan.since(7, enddate, inclusive=False)
        self.assertEqual(datespan_non_inclusive.enddate, datetime(2013, 7, 21, 0, 0, 0))
        self.assertEqual(datespan_non_inclusive.startdate, datetime(2013, 7, 14, 0, 0, 0))


class DateSpanTimezoneTest(SimpleTestCase):

    def test_defaults(self):
        end = datetime.utcnow()
        start = end - timedelta(days=7)
        ds = DateSpan(start, end)
        self.assertEqual(ds.timezone, pytz.utc)

    def test_adjustment(self):
        end = datetime(2014, 3, 7, 2, tzinfo=pytz.utc)
        start = end = datetime(2014, 2, 7, 2, tzinfo=pytz.utc)
        ds = DateSpan(start, end)
        pst = pytz.timezone('US/Pacific')
        ds.set_timezone(pst)
        self.assertEqual(ds.enddate - end, timedelta(hours=8))
        self.assertEqual(ds.startdate - start, timedelta(hours=8))
        self.assertEqual(ds.timezone, pst)


class AddToMonthTest(SimpleTestCase):

    def test_normal_date_function(self):
        self.assertEqual(date(2014, 9, 15), add_months_to_date(date(2014, 7, 15), 2))

    def test_normal_datetime_function(self):
        self.assertEqual(datetime(2014, 9, 15), add_months_to_date(datetime(2014, 7, 15), 2))

    def test_going_backwards(self):
        self.assertEqual(date(2014, 5, 15), add_months_to_date(date(2014, 7, 15), -2))

    def test_no_shift(self):
        self.assertEqual(date(2014, 7, 15), add_months_to_date(date(2014, 7, 15), 0))

    def test_spanning_years(self):
        self.assertEqual(date(2015, 1, 15), add_months_to_date(date(2014, 12, 15), 1))

    def test_spanning_years_backwards(self):
        self.assertEqual(date(2014, 12, 15), add_months_to_date(date(2015, 1, 15), -1))

    def test_spanning_multiple_years(self):
        self.assertEqual(date(2016, 5, 15), add_months_to_date(date(2014, 7, 15), 22))

    def test_spanning_multiple_years_backwards(self):
        self.assertEqual(date(2012, 9, 15), add_months_to_date(date(2014, 7, 15), -22))

    def test_end_of_month(self):
        self.assertEqual(date(2014, 2, 28), add_months_to_date(date(2014, 1, 31), 1))

    def test_leap_year(self):
        self.assertEqual(date(2016, 2, 29), add_months_to_date(date(2016, 1, 31), 1))

    def test_time_preserved(self):
        self.assertEqual(datetime(2014, 8, 15, 10, 30, 11),
                         add_months_to_date(datetime(2014, 7, 15, 10, 30, 11), 1))

    def test_time_preserved_end_of_month(self):
        self.assertEqual(datetime(2014, 2, 28, 10, 30, 11),
                         add_months_to_date(datetime(2014, 1, 31, 10, 30, 11), 1))
