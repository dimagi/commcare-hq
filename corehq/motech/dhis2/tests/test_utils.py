from datetime import date

from nose.tools import assert_equal

from corehq.motech.dhis2.utils import (
    get_previous_month,
    get_previous_quarter,
    get_quarter_start_month,
)


def test_get_previous_month():
    day_start_end = [
        (date(2020, 1, 1), date(2019, 12, 1), date(2019, 12, 31)),
        (date(2020, 12, 31), date(2020, 11, 1), date(2020, 11, 30)),
        (date(2020, 7, 15), date(2020, 6, 1), date(2020, 6, 30)),
    ]
    for day, expected_start, expected_end in day_start_end:
        date_span = get_previous_month(day)
        assert_equal(date_span.startdate, expected_start)
        assert_equal(date_span.enddate, expected_end)


def test_get_previous_quarter():
    day_start_end = [
        (date(2020, 1, 1), date(2019, 10, 1), date(2019, 12, 31)),
        (date(2020, 3, 31), date(2019, 10, 1), date(2019, 12, 31)),
        (date(2020, 10, 1), date(2020, 7, 1), date(2020, 9, 30)),
        (date(2020, 12, 31), date(2020, 7, 1), date(2020, 9, 30)),
        (date(2020, 7, 15), date(2020, 4, 1), date(2020, 6, 30)),
    ]
    for day, expected_start, expected_end in day_start_end:
        date_span = get_previous_quarter(day)
        assert_equal(date_span.startdate, expected_start)
        assert_equal(date_span.enddate, expected_end)


def test_get_quarter_start_month():
    months = range(1, 13)
    start_months = (1, 1, 1, 4, 4, 4, 7, 7, 7, 10, 10, 10)
    for month, expected_month in zip(months, start_months):
        start_month = get_quarter_start_month(month)
        assert_equal(start_month, expected_month)
