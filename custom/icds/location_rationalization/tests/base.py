from unittest import TestCase

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_rationalization.parser import Parser


class BaseTest(TestCase):
    location_types = ['awc', 'supervisor', 'block', 'district', 'state']

    def get_transitions(self):
        filepath = "custom/icds/location_rationalization/tests/data/Location Rationalisation.xlsx"
        return self._load_workbook(filepath)

    def _load_workbook(self, filepath):
        ws = get_workbook(filepath).worksheets[0]
        transitions, errors = Parser(ws, self.location_types).parse()
        return transitions, errors

    def get_errors(self):
        filepath = "custom/icds/location_rationalization/tests/data/Location Rationalisation Bad.xlsx"
        return self._load_workbook(filepath)
