from collections import namedtuple
from unittest import TestCase

from mock import call, patch

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_reassignment.const import (
    ARCHIVED_COLUMN,
    AWC_CODE_COLUMN,
    AWC_NAME_COLUMN,
    CASE_COUNT_COLUMN,
    EXTRACT_OPERATION,
    HOUSEHOLD_ID_COLUMN,
    HOUSEHOLD_MEMBER_DETAILS_COLUMN,
    MERGE_OPERATION,
    MISSING_COLUMN,
    MOVE_OPERATION,
    NEW_LOCATION_CODE_COLUMN,
    OLD_LOCATION_CODE_COLUMN,
    PERSON_CASE_TYPE,
    SPLIT_OPERATION,
    TRANSITION_COLUMN,
)
from custom.icds.location_reassignment.download import Households
from custom.icds.location_reassignment.dumper import Dumper
from custom.icds.location_reassignment.models import Transition

Location = namedtuple('Location', ['location_id', 'site_code'])


class CommCareCaseStub(object):
    def __init__(self, case_id, name, case_json):
        self.case_id = case_id
        self.name = name
        self.case_json = case_json

    def get_case_property(self, case_property):
        return self.case_json.get(case_property)


class TestDumper(TestCase):
    domain = 'test'

    @patch('custom.icds.location_reassignment.dumper.Dumper._old_location_ids_by_site_code')
    @patch('corehq.form_processor.interfaces.dbaccessors.CaseAccessors.get_case_ids_by_owners')
    @patch('corehq.apps.locations.models.SQLLocation.objects.filter')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects.filter')
    def test_dump(self, mock_active_site_codes_search, mock_inactive_site_codes_search, mock_case_count,
                  mock_location_ids):
        mock_case_count.return_value = []
        transitions = {
            'awc': [
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
            ],
            'supervisor': [
                Transition(
                    domain=self.domain,
                    location_type_code='awc',
                    operation=MOVE_OPERATION,
                    old_site_codes=['12'],
                    new_site_codes=['13']),
            ],
            'state': {}
        }

        mock_location_ids.return_value = {
            '111': 'locationid111',
            '113': 'locationid113',
            '114': 'locationid114',
            '116': 'locationid116',
            '119': 'locationid119',
            '12': 'locationid12'
        }
        mock_active_site_codes_search.return_value.values_list.return_value = ['112', '115', '117']
        mock_inactive_site_codes_search.return_value.values_list.return_value = ['120']
        filestream = Dumper(self.domain).dump(transitions)
        workbook = get_workbook(filestream)
        awc_worksheet_rows = list(workbook.get_worksheet('awc'))
        supervisor_worksheet_rows = list(workbook.get_worksheet('supervisor'))
        self.assertEqual(
            supervisor_worksheet_rows,
            [
                {OLD_LOCATION_CODE_COLUMN: '12', TRANSITION_COLUMN: MOVE_OPERATION, NEW_LOCATION_CODE_COLUMN: '13',
                 MISSING_COLUMN: True, ARCHIVED_COLUMN: False, CASE_COUNT_COLUMN: 0}
            ]
        )
        self.assertEqual(
            awc_worksheet_rows,
            [
                {OLD_LOCATION_CODE_COLUMN: '111', TRANSITION_COLUMN: MOVE_OPERATION,
                 NEW_LOCATION_CODE_COLUMN: '112',
                 MISSING_COLUMN: False, ARCHIVED_COLUMN: False, CASE_COUNT_COLUMN: 0},
                {OLD_LOCATION_CODE_COLUMN: '113', TRANSITION_COLUMN: MERGE_OPERATION,
                 NEW_LOCATION_CODE_COLUMN: '115',
                 MISSING_COLUMN: False, ARCHIVED_COLUMN: False, CASE_COUNT_COLUMN: 0},
                {OLD_LOCATION_CODE_COLUMN: '114', TRANSITION_COLUMN: MERGE_OPERATION,
                 NEW_LOCATION_CODE_COLUMN: '115',
                 MISSING_COLUMN: False, ARCHIVED_COLUMN: False, CASE_COUNT_COLUMN: 0},
                {OLD_LOCATION_CODE_COLUMN: '116', TRANSITION_COLUMN: SPLIT_OPERATION,
                 NEW_LOCATION_CODE_COLUMN: '117',
                 MISSING_COLUMN: False, ARCHIVED_COLUMN: False, CASE_COUNT_COLUMN: 0},
                {OLD_LOCATION_CODE_COLUMN: '116', TRANSITION_COLUMN: SPLIT_OPERATION,
                 NEW_LOCATION_CODE_COLUMN: '118',
                 MISSING_COLUMN: True, ARCHIVED_COLUMN: False, CASE_COUNT_COLUMN: 0},
                {OLD_LOCATION_CODE_COLUMN: '119', TRANSITION_COLUMN: EXTRACT_OPERATION,
                 NEW_LOCATION_CODE_COLUMN: '120',
                 MISSING_COLUMN: True, ARCHIVED_COLUMN: True, CASE_COUNT_COLUMN: 0}
            ]
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
        transitions = {
            MOVE_OPERATION: {'112': '111'},  # new: old
            MERGE_OPERATION: {'115': ['113', '114']},  # new: old
            SPLIT_OPERATION: {'116': ['117', '118']},  # old: new
            EXTRACT_OPERATION: {'120': '119'}  # new: old
        }

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
