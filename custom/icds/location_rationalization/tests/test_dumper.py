from mock import patch

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_rationalization.dumper import Dumper
from custom.icds.location_rationalization.tests.base import BaseTest


class TestDumper(BaseTest):
    @patch('corehq.apps.locations.models.SQLLocation.active_objects.filter')
    def test_dump(self, loc_query_patch):
        loc_query_patch.return_value.values_list.return_value = ['11114', '11131']
        transitions, errors = self.get_transitions()
        result_stream = Dumper(self.location_types).dump(transitions)
        result = get_workbook(result_stream).worksheets[0]
        rows = list(result)
        self.assertEqual(
            rows,
            [{'from': '11111', 'transition': 'Merge', 'to': '11114', 'Missing': False},
             {'from': '11112', 'transition': 'Merge', 'to': '11114', 'Missing': False},
             {'from': '11113', 'transition': 'Merge', 'to': '11114', 'Missing': False},
             {'from': '12211', 'transition': 'Split', 'to': '12111', 'Missing': True},
             {'from': '12211', 'transition': 'Split', 'to': '12121', 'Missing': True},
             {'from': '11311', 'transition': 'Rename', 'to': '11211', 'Missing': True},
             {'from': '11312', 'transition': 'Rename', 'to': '11212', 'Missing': True},
             {'from': '11321', 'transition': 'Rename', 'to': '11221', 'Missing': True},
             {'from': '11122', 'transition': 'Extract', 'to': '11131', 'Missing': False}]
        )
