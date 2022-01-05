import os

from django.test import SimpleTestCase
from corehq.apps.case_importer.util import get_spreadsheet
from corehq.util.test_utils import TestFileMixin
from custom.samveg.case_importer.validators import MandatoryColumnsValidator


class TestMandatoryColumnsValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_validate(self):
        with get_spreadsheet(self.get_path('case_upload', 'xlsx')) as spreadsheet:
            errors = MandatoryColumnsValidator.validate(spreadsheet)
        self.assertEqual(
            errors,
            ['Missing columns Rch_id, owner_name, admission_id']
        )
