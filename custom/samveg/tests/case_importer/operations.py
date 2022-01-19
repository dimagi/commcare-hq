from datetime import datetime

from django.test import SimpleTestCase

import pytz

from custom.samveg.case_importer.operations import AddCustomCaseProperties


class TestAddCustomCaseProperties(SimpleTestCase):
    def test_added_case_properties(self):
        fields_to_update = {}
        fields_to_update, errors = AddCustomCaseProperties.run(1, {}, fields_to_update, {})
        self.assertEqual(
            fields_to_update['last_upload_change'],
            str(datetime.utcnow().astimezone(pytz.timezone('Asia/Kolkata')).date())
        )
