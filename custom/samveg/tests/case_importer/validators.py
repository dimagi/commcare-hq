import os

from django.test import SimpleTestCase

from corehq.apps.case_importer.util import get_spreadsheet
from corehq.util.test_utils import TestFileMixin
from custom.samveg.case_importer.validators import MandatoryColumnsValidator
from custom.samveg.const import MANDATORY_COLUMNS, NEWBORN_WEIGHT_COLUMN


class TestMandatoryColumnsValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_unexpected_sheet(self):
        with get_spreadsheet(self.get_path('unexpected_sheet_case_upload', 'xlsx')) as spreadsheet:
            errors = MandatoryColumnsValidator.run(spreadsheet)
        self.assertEqual(
            errors,
            ['Unexpected sheet uploaded']
        )

    def test_validate_missing_columns(self):
        with get_spreadsheet(self.get_path('missing_columns_rch_case_upload', 'xlsx')) as spreadsheet:
            errors = MandatoryColumnsValidator.run(spreadsheet)
        # extract missing columns from message
        missing_columns = set(errors[0].split('Missing columns ')[1].split(', '))
        expected_missing_columns = set(MANDATORY_COLUMNS)
        self.assertEqual(
            missing_columns,
            expected_missing_columns
        )

        with get_spreadsheet(self.get_path('missing_columns_sncu_case_upload', 'xlsx')) as spreadsheet:
            errors = MandatoryColumnsValidator.run(spreadsheet)
        # extract missing columns from message
        missing_columns = set(errors[0].split('Missing columns ')[1].split(', '))
        expected_missing_columns = set(MANDATORY_COLUMNS)
        expected_missing_columns.add(NEWBORN_WEIGHT_COLUMN)
        self.assertEqual(
            missing_columns,
            expected_missing_columns
        )
