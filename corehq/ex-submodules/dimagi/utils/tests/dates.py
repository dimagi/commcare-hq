from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta, date
from six.moves.urllib.parse import urlencode
import pytz
from dimagi.utils.dates import DateSpan, add_months_to_date
from django.test import SimpleTestCase
from django.http import HttpRequest, QueryDict
from dimagi.utils.decorators.datespan import datespan_in_request


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


class DateSpanInRequestTest(SimpleTestCase):
    def setUp(self):
        self.datespan_decorator = datespan_in_request(
            from_param="startdate",
            to_param="enddate",
            default_days=7,
            format_string='%Y-%m-%dT%H:%M:%S'
        )

    def test_from_request(self):
        start_date = datetime(2013, 7, 21, 0, 0, 0)
        end_date = datetime(2013, 7, 15, 0, 0, 0)
        request = HttpRequest()
        query_string = urlencode({
            'startdate': start_date.isoformat(),
            'enddate': end_date.isoformat()}
        )
        request.GET = QueryDict(query_string)
        datespan_in_request()

        @self.datespan_decorator
        def dummy(req):
            return getattr(req, 'datespan', None)

        datespan = dummy(request)
        self.assertIsNotNone(datespan)
        self.assertIsInstance(datespan, DateSpan)
        self.assertEqual(datespan.enddate, end_date)
        self.assertEqual(datespan.startdate, start_date)


class DateSpanValidationTests(SimpleTestCase):

    def test_ok(self):
        datespan = DateSpan(datetime(2015, 1, 1), datetime(2015, 2, 1))
        self.assertTrue(datespan.is_valid())
        self.assertEqual(datespan.get_validation_reason(), "")

    def test_date_missing(self):
        datespan = DateSpan(datetime(2015, 1, 1), None)
        self.assertFalse(datespan.is_valid())
        self.assertEqual(datespan.get_validation_reason(), "You have to specify both dates!")

    def test_end_before_start(self):
        startdate = datetime(2015, 2, 1)
        enddate = datetime(2015, 1, 1)
        datespan = DateSpan(startdate, enddate)
        self.assertFalse(datespan.is_valid())
        self.assertEqual(datespan.get_validation_reason(),
                         "You can't have an end date of %s after start date of %s" % (enddate, startdate))

    def test_wrong_century(self):
        datespan = DateSpan(datetime(1815, 1, 1), datetime(1815, 2, 1))
        self.assertFalse(datespan.is_valid())
        self.assertEqual(datespan.get_validation_reason(), "You can't use dates earlier than the year 1900")

    def test_datespan_ok(self):
        datespan = DateSpan(datetime(2015, 1, 1), datetime(2015, 4, 1), max_days=90)
        self.assertTrue(datespan.is_valid())

    def test_datespan_too_long(self):
        datespan = DateSpan(datetime(2015, 1, 1), datetime(2015, 7, 1), max_days=90)
        self.assertFalse(datespan.is_valid())
        self.assertEqual(datespan.get_validation_reason(),
                         "You are limited to a span of 90 days, but this date range spans 181 days")

    def test_negative_max_days(self):
        with self.assertRaisesRegex(ValueError, 'max_days cannot be less than 0'):
            DateSpan(datetime(2015, 1, 1), datetime(2015, 4, 1), max_days=-1)
