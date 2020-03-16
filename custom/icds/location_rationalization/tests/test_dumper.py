from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_rationalization.dumper import Dumper
from custom.icds.location_rationalization.tests.base import BaseTest


class TestDumper(BaseTest):
    def test_dump(self):
        transitions, errors = self.get_transitions()
        result_stream = Dumper(self.location_types).dump(transitions)
        result = get_workbook(result_stream).worksheets[0]
        rows = list(result)
        self.assertEqual(
            rows,
            [{'from': '11111', 'transition': 'Merge', 'to': '11114'},
             {'from': '11112', 'transition': 'Merge', 'to': '11114'},
             {'from': '11113', 'transition': 'Merge', 'to': '11114'},
             {'from': '12211', 'transition': 'Split', 'to': '12111'},
             {'from': '12211', 'transition': 'Split', 'to': '12121'},
             {'from': '11311', 'transition': 'Rename', 'to': '11211'},
             {'from': '11312', 'transition': 'Rename', 'to': '11212'},
             {'from': '11321', 'transition': 'Rename', 'to': '11221'},
             {'from': '11122', 'transition': 'Extract', 'to': '11131'}]
        )
