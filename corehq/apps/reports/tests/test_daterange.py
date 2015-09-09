from django.test import SimpleTestCase
from corehq.apps.reports.daterange import get_simple_dateranges, get_daterange_start_end_dates, \
    get_complex_dateranges
from corehq.apps.reports.exceptions import InvalidDaterangeException


class DateRangeTest(SimpleTestCase):

    def test_no_exceptions_on_simple_calls(self):
        for daterange in get_simple_dateranges():
            get_daterange_start_end_dates(daterange.slug)

    def test_exceptions_on_complex_calls(self):
        for daterange in get_complex_dateranges():
            with self.assertRaises(InvalidDaterangeException):
                get_daterange_start_end_dates(daterange.slug)
