from __future__ import absolute_import
from datetime import datetime
from django.test import SimpleTestCase
from corehq.util.dates import get_quarter_date_range, get_quarter_for_date
from corehq.util.test_utils import generate_cases


class TestQuarterRanges(SimpleTestCase):
    pass


@generate_cases(
    (
        (2016, 1, datetime(2016, 1, 1), datetime(2016, 4, 1)),
        (2016, 2, datetime(2016, 4, 1), datetime(2016, 7, 1)),
        (2016, 3, datetime(2016, 7, 1), datetime(2016, 10, 1)),
        (2016, 4, datetime(2016, 10, 1), datetime(2017, 1, 1)),
        (2017, 1, datetime(2017, 1, 1), datetime(2017, 4, 1)),
    ),
    cls=TestQuarterRanges
)
def test_quarter_ranges(self, year, quarter, expected_start, expected_end):
    startdate, enddate = get_quarter_date_range(year, quarter)
    self.assertEqual(expected_start, startdate)
    self.assertEqual(expected_end, enddate)


@generate_cases(
    (
        (2016, 0),
        (2016, 5),
        (2016, None),
        (2016, 'eleventy'),
    ),
    cls=TestQuarterRanges
)
def test_invalid_quarters(self, year, quarter):
    with self.assertRaises(AssertionError):
        get_quarter_date_range(year, quarter)


@generate_cases(
    (
        (datetime(2016, 1, 1), 2016, 1),
        (datetime(2016, 2, 1), 2016, 1),
        (datetime(2016, 3, 1), 2016, 1),
        (datetime(2016, 4, 1), 2016, 2),
        (datetime(2016, 5, 1), 2016, 2),
        (datetime(2016, 6, 1), 2016, 2),
        (datetime(2016, 7, 1), 2016, 3),
        (datetime(2016, 8, 1), 2016, 3),
        (datetime(2016, 9, 1), 2016, 3),
        (datetime(2016, 10, 1), 2016, 4),
        (datetime(2016, 11, 1), 2016, 4),
        (datetime(2016, 12, 1), 2016, 4),
        (datetime(2017, 1, 1), 2017, 1),
    ),
    cls=TestQuarterRanges
)
def test_get_quarter_for_date(self, input_date, year, quarter):
    self.assertEqual((year, quarter), get_quarter_for_date(input_date))
