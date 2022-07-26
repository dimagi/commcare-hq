from datetime import datetime
from unittest.mock import patch

from django.test import SimpleTestCase

from custom.samveg.case_importer.operations import AddCustomCaseProperties


class TestAddCustomCaseProperties(SimpleTestCase):
    def test_added_case_properties(self):
        fields_to_update = {'Call1': '2021-01-01'}
        with patch('custom.samveg.case_importer.operations._get_today_date') as today_patch:
            today_patch.return_value = datetime(2020, 1, 1).date()
            fields_to_update, _ = AddCustomCaseProperties(fields_to_update=fields_to_update).run()

        self.assertDictEqual(
            fields_to_update,
            {
                'Call1': '2021-01-01',
                'last_upload_change': '2020-01-01',
                'visit_type': 'anc'
            }
        )
