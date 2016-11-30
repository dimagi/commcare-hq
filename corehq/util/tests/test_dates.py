from datetime import datetime
from django.test import SimpleTestCase
from corehq.util.dates import get_quarter_date_range
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
