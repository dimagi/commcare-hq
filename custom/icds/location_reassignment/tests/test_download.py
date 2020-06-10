from unittest import TestCase

from mock import call, patch

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_reassignment.const import (
    AWC_CODE_COLUMN,
    AWC_NAME_COLUMN,
    EXTRACT_OPERATION,
    HOUSEHOLD_ID_COLUMN,
    HOUSEHOLD_MEMBER_DETAILS_COLUMN,
    MERGE_OPERATION,
    MOVE_OPERATION,
    PERSON_CASE_TYPE,
    SPLIT_OPERATION,
)
from custom.icds.location_reassignment.download import Households
from custom.icds.location_reassignment.models import Transition
from custom.icds.location_reassignment.tests.utils import (
    CommCareCaseStub,
    Location,
)


class TestHouseholds(TestCase):
    domain = 'test'

    @patch('custom.icds.location_reassignment.download.get_household_child_cases_by_owner')
    @patch('corehq.form_processor.interfaces.dbaccessors.CaseAccessors.get_case')
    @patch('custom.icds.location_reassignment.download.get_household_case_ids')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects.get')
    def test_dump(self, get_location_mock, get_household_case_ids_mock, case_accessor_mock, child_cases_mock):
        location = Location(site_code='123', location_id='123654789')
        get_location_mock.return_value = location
        get_household_case_ids_mock.return_value = ['1', '2']
        case_accessor_mock.return_value = CommCareCaseStub(
            '100', 'A House', {'hh_reg_date': '20/1/1988', 'hh_religion': 'Above All'})
        child_cases_mock.return_value = [
            CommCareCaseStub('101', 'A Person', {'age_at_reg': '4', 'sex': 'M'}),
            CommCareCaseStub('102', 'B Person', {'age_at_reg': '5', 'sex': 'F'}),
        ]
        transitions = [
            Transition(
                domain=self.domain,
                location_type_code='awc',
                operation=MOVE_OPERATION,
                old_site_codes=['111'],
                new_site_codes=['112']),
            Transition(
                domain=self.domain,
                location_type_code='awc',
                operation=MERGE_OPERATION,
                old_site_codes=['113', '114'],
                new_site_codes=['115']),
            Transition(
                domain=self.domain,
                location_type_code='awc',
                operation=SPLIT_OPERATION,
                old_site_codes=['116'],
                new_site_codes=['117', '118']),
            Transition(
                domain=self.domain,
                location_type_code='awc',
                operation=EXTRACT_OPERATION,
                old_site_codes=['119'],
                new_site_codes=['120'])
        ]

        filestream = Households(self.domain).dump(transitions)

        get_location_mock.assert_has_calls([
            call(domain='test', site_code='116'),
            call(domain='test', site_code='119')
        ])
        get_household_case_ids_mock.assert_has_calls([
            call(self.domain, location.location_id),
            call(self.domain, location.location_id)
        ])
        case_accessor_mock.assert_has_calls([
            call('1'), call('2')
        ])
        child_cases_mock.assert_has_calls([
            call(self.domain, '1', location.location_id, [PERSON_CASE_TYPE]),
            call(self.domain, '2', location.location_id, [PERSON_CASE_TYPE])
        ])

        workbook = get_workbook(filestream)
        self.assertEqual(len(workbook.worksheets), 2)
        expected_row = {
            AWC_NAME_COLUMN: '',
            AWC_CODE_COLUMN: '',
            'Name of Household': 'A House',
            'Date of Registration': '20/1/1988',
            'Religion': 'Above All',
            'Caste': '',
            'APL/BPL': '',
            'Number of Household Members': 2,
            HOUSEHOLD_MEMBER_DETAILS_COLUMN: 'A Person (4/M), B Person (5/F)',
            HOUSEHOLD_ID_COLUMN: '100'
        }
        worksheet1_rows = list(workbook.worksheets_by_title['116'])
        self.assertEqual(
            worksheet1_rows,
            [expected_row, expected_row]
        )
        worksheet2_rows = list(workbook.worksheets_by_title['119'])
        self.assertEqual(
            worksheet2_rows,
            [expected_row, expected_row]
        )
