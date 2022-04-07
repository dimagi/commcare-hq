from datetime import datetime, timezone

from nose.tools import assert_equal, assert_not_equal
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay


def test_happy_case_display():
    case_dict = {
        'name': 'Foo',
        'modified_on': '2022-04-06T12:13:14Z',
    }
    case_display = CaseDisplay(case_dict)
    assert_equal(case_display.modified_on, 'Apr 06, 2022 12:13:14 UTC')


def test_bad_case_display():
    case_dict = {
        'name': "It's a trap",
        'modified_on': 'broken',
    }
    case_display = CaseDisplay(case_dict)
    assert_equal(case_display.modified_on, '')


def test_parse_date_iso_datetime():
    parsed = CaseDisplay({}).parse_date('2022-04-06T12:13:14Z')
    assert_equal(parsed, datetime(2022, 4, 6, 12, 13, 14))
    # `date` is timezone naive
    assert_not_equal(parsed, datetime(2022, 4, 6, 12, 13, 14,
                                      tzinfo=timezone.utc))


def test_parse_date_noniso_datetime():
    parsed = CaseDisplay({}).parse_date('Apr 06, 2022 12:13:14 UTC')
    assert_equal(parsed, datetime(2022, 4, 6, 12, 13, 14))
    assert_not_equal(parsed, datetime(2022, 4, 6, 12, 13, 14,
                                      tzinfo=timezone.utc))


def test_parse_date_date():
    parsed = CaseDisplay({}).parse_date('2022-04-06')
    assert_equal(parsed, datetime(2022, 4, 6, 0, 0, 0))


def test_parse_date_str():
    parsed = CaseDisplay({}).parse_date('broken')
    assert_equal(parsed, 'broken')


def test_parse_date_none():
    parsed = CaseDisplay({}).parse_date(None)
    assert_equal(parsed, None)


def test_parse_date_int():
    parsed = CaseDisplay({}).parse_date(4)
    assert_equal(parsed, 4)
