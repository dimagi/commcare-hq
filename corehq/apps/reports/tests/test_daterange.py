import datetime

from django.test import SimpleTestCase

from mock import patch

from corehq.apps.reports.daterange import (
    get_all_daterange_choices,
    get_daterange_start_end_dates,
    get_simple_dateranges,
)
from corehq.apps.reports.exceptions import InvalidDaterangeException


class DateRangeTest(SimpleTestCase):

    def test_no_exceptions_on_simple_calls(self):
        for daterange in get_simple_dateranges():
            get_daterange_start_end_dates(daterange.slug)

    def test_exceptions_on_complex_calls(self):
        for daterange in [choice for choice in get_all_daterange_choices() if not choice.simple]:
            with self.assertRaises(InvalidDaterangeException):
                get_daterange_start_end_dates(daterange.slug)


class KnownRangesTests(SimpleTestCase):

    def setUp(self):
        # The first performance of the William Tell overture. You know, to test the known ranges.
        self.first_performance = datetime.date(year=1829, month=8, day=3)
        # Ta da dum, ta da dum, ta da dum dum dum.

    @patch('datetime.date')
    def test_since(self, date_patch):
        date_patch.today.return_value = self.first_performance

        saturday = datetime.date(year=1829, month=8, day=1)
        start_date, end_date = get_daterange_start_end_dates('since', start_date=saturday)
        self.assertEqual(start_date, saturday)
        self.assertEqual(end_date, self.first_performance)

    def test_range(self):
        # Zane Grey dedicated his book "The Lone Star Ranger" to Texas Ranger Captain John R. Hughes in 1915
        john_hughes_birthday = datetime.date(year=1855, month=2, day=11)

        start_date, end_date = get_daterange_start_end_dates(
            'range',
            start_date=self.first_performance,
            end_date=john_hughes_birthday,
        )
        self.assertEqual(start_date, self.first_performance)
        self.assertEqual(end_date, john_hughes_birthday)

    @patch('datetime.date')
    def test_thismonth(self, date_patch):
        date_patch.today.return_value = self.first_performance

        start_date, end_date = get_daterange_start_end_dates('thismonth')
        self.assertEqual(start_date, datetime.date(year=1829, month=8, day=1))
        self.assertEqual(end_date, self.first_performance)

    @patch('datetime.date')
    def test_lastmonth(self, date_patch):
        date_patch.today.return_value = self.first_performance

        start_date, end_date = get_daterange_start_end_dates('lastmonth')
        self.assertEqual(start_date, datetime.date(year=1829, month=7, day=1))
        self.assertEqual(end_date, datetime.date(year=1829, month=7, day=31))

    @patch('datetime.date')
    def test_lastyear(self, date_patch):
        date_patch.today.return_value = self.first_performance

        start_date, end_date = get_daterange_start_end_dates('lastyear')
        self.assertEqual(start_date, datetime.date(year=1828, month=1, day=1))
        self.assertEqual(end_date, datetime.date(year=1828, month=12, day=31))

    def test_last7(self):
        date_class = datetime.date
        with patch('datetime.date') as date_patch:
            date_patch.today.return_value = self.first_performance
            date_patch.side_effect = lambda *args, **kwargs: date_class(*args, **kwargs)

            start_date, end_date = get_daterange_start_end_dates('last7')
            self.assertEqual(start_date, datetime.date(year=1829, month=7, day=27))
            self.assertEqual(end_date, self.first_performance)

    def test_last30(self):
        date_class = datetime.date
        with patch('datetime.date') as date_patch:
            date_patch.today.return_value = self.first_performance
            date_patch.side_effect = lambda *args, **kwargs: date_class(*args, **kwargs)

            start_date, end_date = get_daterange_start_end_dates('last30')
            self.assertEqual(start_date, datetime.date(year=1829, month=7, day=4))  # Woo!
            self.assertEqual(end_date, self.first_performance)

    def test_lastn(self):
        date_class = datetime.date
        with patch('datetime.date') as date_patch:
            date_patch.today.return_value = self.first_performance
            date_patch.side_effect = lambda *args, **kwargs: date_class(*args, **kwargs)

            start_date, end_date = get_daterange_start_end_dates('lastn', days=-14)  # In two weeks' time
            self.assertEqual(start_date, datetime.date(year=1829, month=8, day=17))
            self.assertEqual(end_date, self.first_performance)
            # TODO: If the start date occurs after the end date, we should switch them.
