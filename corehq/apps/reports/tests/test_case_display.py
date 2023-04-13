import uuid

from django.test import TestCase

from nose.tools import assert_equal

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.views import CaseDisplayWrapper

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.reports.standard.cases.data_sources import CaseDisplayES
from corehq.form_processor.models import CommCareCase


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


class TestCaseDisplayWrapper(TestCase):
    domain = 'test-case-display-wrapper'

    def test_location_id_case_property(self):
        case_id = uuid.uuid4().hex
        location_name = 'location'
        submit_case_blocks([CaseBlock(
            case_id=case_id,
            create=True,
            update={'location_id': location_name}
        ).as_text()], domain=self.domain)
        case = CommCareCase.objects.get_case(case_id, self.domain)
        case_properties = CaseDisplayWrapper(case).dynamic_properties()
        self.assertTrue('location_id' in case_properties)
        self.assertEqual(location_name, case_properties['location_id'])
