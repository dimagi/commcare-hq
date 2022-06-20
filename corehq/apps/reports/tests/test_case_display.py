from nose.tools import assert_equal

from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES


def test_happy_case_display():
    case_dict = {
        'name': 'Foo',
        'modified_on': '2022-04-06T12:13:14Z',
    }
    case_display = CaseDisplayES(case_dict)
    assert_equal(case_display.modified_on, 'Apr 06, 2022 12:13:14 UTC')
    assert_equal(case_display.last_modified, 'Apr 06, 2022 12:13:14 UTC')


def test_bad_case_display():
    case_dict = {
        'name': "It's a trap",
        'modified_on': 'broken',
    }
    case_display = CaseDisplayES(case_dict)
    assert_equal(case_display.modified_on, '')


def test_blank_owner_id():
    # previously this would error
    owner_type, meta = CaseDisplayES({}).owner
    assert_equal(owner_type, 'user')
    assert_equal(meta, {'id': '', 'name': ''})


def test_null_owner_id():
    # previously this would error
    owner_type, meta = CaseDisplayES({'owner_id': None}).owner
    assert_equal(owner_type, 'user')
    assert_equal(meta, {'id': None, 'name': None})
