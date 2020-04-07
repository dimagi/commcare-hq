from unittest import TestCase

from mock import patch

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_reassignment.const import (
    ARCHIVED_COLUMN,
    CASE_COUNT_COLUMN,
    EXTRACT_OPERATION,
    MERGE_OPERATION,
    MISSING_COLUMN,
    MOVE_OPERATION,
    NEW_LOCATION_CODE_COLUMN,
    OLD_LOCATION_CODE_COLUMN,
    SPLIT_OPERATION,
    TRANSITION_COLUMN,
)
from custom.icds.location_reassignment.dumper import Dumper


class TestDumper(TestCase):
    domain = "test"

    @patch('custom.icds.location_reassignment.dumper.Dumper._old_location_ids_by_site_code')
    @patch('corehq.form_processor.interfaces.dbaccessors.CaseAccessors.get_case_ids_by_owners')
    @patch('corehq.apps.locations.models.SQLLocation.objects.filter')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects.filter')
    def test_dump(self, mock_active_site_codes_search, mock_inactive_site_codes_search, mock_case_count,
                  mock_location_ids):
        mock_case_count.return_value = []
        transitions = {
            'awc': {
                MOVE_OPERATION: {'112': '111'},  # new: old
                MERGE_OPERATION: {'115': ['113', '114']},  # new: old
                SPLIT_OPERATION: {'116': ['117', '118']},  # old: new
                EXTRACT_OPERATION: {'120': '119'}  # new: old
            },
            'supervisor': {
                MOVE_OPERATION: {'13': '12'}
            },
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
