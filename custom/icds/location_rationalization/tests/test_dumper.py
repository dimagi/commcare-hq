from mock import patch

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_rationalization.dumper import Dumper
from custom.icds.location_rationalization.tests.base import BaseTest


class TestDumper(BaseTest):
    @patch('corehq.apps.locations.models.SQLLocation.inactive_objects.filter')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects.filter')
    def test_dump(self, loc_active_query_patch, loc_inactive_query_patch):
        loc_active_query_patch.return_value.values_list.return_value = ['11114', '11131']
        loc_inactive_query_patch.return_value.values_list.return_value = ['1122', '11221']
        transitions, errors = self.get_transitions()
        result_stream = Dumper(self.location_types).dump(transitions)
        workbook = get_workbook(result_stream)
        self.assertEqual(
            list(workbook.worksheets_by_title['awc']),
            [{'from': '11111', 'transition': 'Merge', 'to': '11114', 'Missing': False, 'Archived': False},
             {'from': '11112', 'transition': 'Merge', 'to': '11114', 'Missing': False, 'Archived': False},
             {'from': '11113', 'transition': 'Merge', 'to': '11114', 'Missing': False, 'Archived': False},
             {'from': '12211', 'transition': 'Split', 'to': '12111', 'Missing': True, 'Archived': False},
             {'from': '12211', 'transition': 'Split', 'to': '12121', 'Missing': True, 'Archived': False},
             {'from': '11311', 'transition': 'Rename', 'to': '11211', 'Missing': True, 'Archived': False},
             {'from': '11312', 'transition': 'Rename', 'to': '11212', 'Missing': True, 'Archived': False},
             {'from': '11321', 'transition': 'Rename', 'to': '11221', 'Missing': True, 'Archived': True},
             {'from': '11122', 'transition': 'Extract', 'to': '11131', 'Missing': False, 'Archived': False}]
        )
        self.assertEqual(
            list(workbook.worksheets_by_title['supervisor']),
            [{'from': '1221', 'transition': 'Split', 'to': '1211', 'Missing': True, 'Archived': False},
             {'from': '1221', 'transition': 'Split', 'to': '1212', 'Missing': True, 'Archived': False},
             {'from': '1131', 'transition': 'Rename', 'to': '1121', 'Missing': True, 'Archived': False},
             {'from': '1132', 'transition': 'Rename', 'to': '1122', 'Missing': True, 'Archived': True}]
        )
        self.assertEqual(
            list(workbook.worksheets_by_title['block']),
            [{'from': '113', 'transition': 'Rename', 'to': '112', 'Missing': True, 'Archived': False}]
        )
        self.assertEqual(
            list(workbook.worksheets_by_title['district']),
            []
        )
        self.assertEqual(
            list(workbook.worksheets_by_title['state']),
            []
        )
