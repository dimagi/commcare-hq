from nose.tools import assert_equal
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
