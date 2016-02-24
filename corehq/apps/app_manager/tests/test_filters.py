import datetime
from collections import namedtuple
from contextlib import contextmanager
from django.test import SimpleTestCase
from mock import patch
from corehq.apps.app_manager.models import CustomMonthFilter


Date = namedtuple('Date', ('year', 'month', 'day'))


MAY_15 = Date(2015, 5, 15)
MAY_20 = Date(2015, 5, 20)
MAY_21 = Date(2015, 5, 21)


@contextmanager
def patch_today(year, month, day):
    date_class = datetime.date
    with patch('datetime.date') as date_patch:
        date_patch.today.return_value = date_class(year, month, day)
        date_patch.side_effect = lambda *args, **kwargs: date_class(*args, **kwargs)
        yield date_patch


class CustomMonthFilterTests(SimpleTestCase):

    def setUp(self):
        self.date_class = datetime.date

    # Assume it was May 15:
    # Period 0, day 21, you would sync April 21-May 15th
    # Period 1, day 21, you would sync March 21-April 20th
    # Period 2, day 21, you would sync February 21-March 20th

    def test_may15_period0(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=21, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=21))
            self.assertEqual(date_span.enddate, self.date_class(*MAY_15))

    def test_may15_period1(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=21, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=20))

    def test_may15_period2(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=21, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=2, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=3, day=20))

    # Assume it was May 20:
    # Period 0, day 21, you would sync April 21-May 20th
    # Period 1, day 21, you would sync March 21-April 20th
    # Period 2, day 21, you would sync February 21-March 20th

    def test_may20_period0(self):
        with patch_today(*MAY_20):
            filter_ = CustomMonthFilter(start_of_month=21, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=21))
            self.assertEqual(date_span.enddate, self.date_class(*MAY_20))

    def test_may20_period1(self):
        with patch_today(*MAY_20):
            filter_ = CustomMonthFilter(start_of_month=21, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=20))

    def test_may20_period2(self):
        with patch_today(*MAY_20):
            filter_ = CustomMonthFilter(start_of_month=21, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=2, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=3, day=20))

    # Assume it was May 21:
    # Period 0, day 21, you would sync May 21-May 21th
    # Period 1, day 21, you would sync April 21-May 20th
    # Period 2, day 21, you would sync March 21-April 20th

    def test_may21_period0(self):
        with patch_today(*MAY_21):
            filter_ = CustomMonthFilter(start_of_month=21, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(*MAY_21))
            self.assertEqual(date_span.enddate, self.date_class(*MAY_21))

    def test_may21_period1(self):
        with patch_today(*MAY_21):
            filter_ = CustomMonthFilter(start_of_month=21, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=21))
            self.assertEqual(date_span.enddate, self.date_class(*MAY_20))

    def test_may21_period2(self):
        with patch_today(*MAY_21):
            filter_ = CustomMonthFilter(start_of_month=21, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=20))

    # May 15 for 10 days from the end of the month (start_of_month = -10):
    # Period 0, day 21, you would sync April 21-May 15th
    # Period 1, day 21, you would sync March 21-April 20th
    # Period 2, day 21, you would sync February 18-March 20th

    def test_may15_minus10_period0(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=-10, period=0)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=4, day=21))
            self.assertEqual(date_span.enddate, self.date_class(*MAY_15))

    def test_may15_minus10_period1(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=-10, period=1)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=3, day=21))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=4, day=20))

    def test_may15_minus10_period2(self):
        with patch_today(*MAY_15):
            filter_ = CustomMonthFilter(start_of_month=-10, period=2)
            date_span = filter_.get_filter_value(user=None, ui_filter=None)
            self.assertEqual(date_span.startdate, self.date_class(year=2015, month=2, day=18))
            self.assertEqual(date_span.enddate, self.date_class(year=2015, month=3, day=20))
