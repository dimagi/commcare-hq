import os

from django.test import SimpleTestCase

from corehq.apps.case_importer.util import get_spreadsheet
from corehq.util.test_utils import TestFileMixin
from custom.samveg.case_importer.validators import (
    CallValidator,
    MandatoryColumnsValidator,
    MandatoryValueValidator,
    UploadLimitValidator,
)
from custom.samveg.const import (
    MANDATORY_COLUMNS,
    NEWBORN_WEIGHT_COLUMN,
    OWNER_NAME,
    ROW_LIMIT_PER_OWNER_PER_CALL_TYPE,
)


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

    def test_validate_mandatory_columns(self):
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

    def _assert_missing_values_for_sheet(self, spreadsheet_name, mandatory_values):
        with get_spreadsheet(self.get_path(spreadsheet_name, 'xlsx')) as spreadsheet:
            for row_num, raw_row in enumerate(spreadsheet.iter_row_dicts()):
                if row_num == 0:
                    continue  # skip first row (header row)
                fields_to_update, error_messages = MandatoryValueValidator.run(row_num, raw_row, raw_row)
                self.assertEqual(
                    error_messages[0],
                    f"Mandatory columns {', '.join(mandatory_values)}"
                )

    def test_validate_mandatory_values(self):
        mandatory_values = ['name', 'MobileNo', 'DIST_NAME', 'Health_Block', 'visit_type', 'owner_name', 'Rch_id']
        self._assert_missing_values_for_sheet('missing_values_rch_case_upload', mandatory_values)

        mandatory_values = ['name', 'MobileNo', 'DIST_NAME', 'Health_Block', 'visit_type',
                            'owner_name', 'admission_id', 'newborn_weight']
        self._assert_missing_values_for_sheet('missing_values_sncu_case_upload', mandatory_values)


class TestCallValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_missing_call_column(self):
        raw_row = _sample_valid_rch_upload()
        raw_row.pop('Call1')
        row_num = 1

        fields_to_update, error_messages = CallValidator.run(row_num, raw_row, raw_row)

        self.assertEqual(
            error_messages,
            ['Missing call details']
        )

    def test_invalid_call_value(self):
        raw_row = _sample_valid_rch_upload()
        raw_row['Call1'] = 'abc'
        row_num = 1

        fields_to_update, error_messages = CallValidator.run(row_num, raw_row, raw_row)

        self.assertEqual(
            error_messages,
            ['Could not parse latest call date']
        )

    def test_call_value_not_in_last_month(self):
        raw_row = _sample_valid_rch_upload()
        row_num = 1

        fields_to_update, error_messages = CallValidator.run(row_num, raw_row, raw_row)

        self.assertEqual(
            error_messages,
            ['Latest call not in last month']
        )


class TestUploadLimitValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_update_counter(self):
        raw_row = _sample_valid_rch_upload()
        row_num = 1
        import_context = {}

        fields_to_update, error_messages = UploadLimitValidator.run(row_num, raw_row, raw_row, import_context)

        self.assertEqual(
            import_context['counter']['watson']['Call1'],
            1
        )
        self.assertEqual(len(error_messages), 0)

    def test_upload_limit(self):
        raw_row = _sample_valid_rch_upload()
        row_num = 1
        # initialize context to replicate limit reached
        import_context = {'counter': {raw_row[OWNER_NAME]: {'Call1': ROW_LIMIT_PER_OWNER_PER_CALL_TYPE}}}

        fields_to_update, error_messages = UploadLimitValidator.run(row_num, raw_row, raw_row, import_context)

        self.assertEqual(
            error_messages,
            ['Limit reached for watson for call 1']
        )

    def test_missing_call_column(self):
        raw_row = _sample_valid_rch_upload()
        raw_row.pop('Call1')
        row_num = 1

        fields_to_update, error_messages = UploadLimitValidator.run(row_num, raw_row, raw_row, {})

        self.assertEqual(
            error_messages,
            ['Missing owner or call details']
        )


def _sample_valid_rch_upload():
    return {
        'Rch_id': 98765,
        'name': 'Sherlock',
        'MobileNo': 9999999999,
        'DIST_NAME': 'USA',
        'Health_Block': 'DC',
        'visit_type': 'investigation',
        'owner_name': 'watson',
        'Call1': '10-10-21'
    }
