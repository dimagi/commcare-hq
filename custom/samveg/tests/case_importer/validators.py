import os

from django.test import SimpleTestCase

from corehq.apps.case_importer.util import get_spreadsheet
from corehq.util.test_utils import TestFileMixin
from custom.samveg.case_importer.validators import (
    MandatoryColumnsValidator,
    MandatoryValueValidator,
)
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


class TestMandatoryValueValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def _assert_missing_values_for_sheet(self, spreadsheet_name, expected_missing_values_for_rows):
        with get_spreadsheet(self.get_path(spreadsheet_name, 'xlsx')) as spreadsheet:
            for row_num, raw_row in enumerate(spreadsheet.iter_row_dicts()):
                if row_num == 0:
                    continue  # skip first row (header row)
                fields_to_update, error_messages = MandatoryValueValidator.run(row_num, raw_row, raw_row)
                missing_values = set(error_messages[0].split('Missing values for ')[1].split(', '))
                self.assertEqual(
                    missing_values,
                    expected_missing_values_for_rows[row_num - 1]
                )

    def test_validate_mandatory_values(self):
        expected_missing_values_for_rows = [
            {'Rch_id', 'Health_Block', 'visit_type', 'owner_name'},
            {'MobileNo', 'Health_Block', 'visit_type'}
        ]
        self._assert_missing_values_for_sheet('missing_values_rch_case_upload', expected_missing_values_for_rows)

        expected_missing_values_for_rows = [
            {'admission_id', 'Health_Block', 'visit_type', 'owner_name'},
            {'MobileNo', 'Health_Block', 'visit_type', 'newborn_weight'}
        ]
        self._assert_missing_values_for_sheet('missing_values_sncu_case_upload', expected_missing_values_for_rows)
