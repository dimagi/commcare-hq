import datetime
import os

from django.test import SimpleTestCase, TestCase

from dateutil.relativedelta import relativedelta

from corehq.apps.case_importer.util import get_spreadsheet
from corehq.apps.domain.models import Domain, OperatorCallLimitSettings
from corehq.util.test_utils import TestFileMixin
from custom.samveg.case_importer.exceptions import CallValueInvalidError
from custom.samveg.case_importer.validators import (
    CallColumnsValidator,
    CallValidator,
    FormatValidator,
    RequiredColumnsValidator,
    RequiredValueValidator,
    UploadLimitValidator,
)
from custom.samveg.commcare_extensions import samveg_case_upload_row_operations
from custom.samveg.const import (
    NEWBORN_WEIGHT_COLUMN,
    OWNER_NAME,
    RCH_BENEFICIARY_IDENTIFIER,
    REQUIRED_COLUMNS,
    SKIP_CALL_VALIDATOR,
    SKIP_CALL_VALIDATOR_YES,
    SNCU_BENEFICIARY_IDENTIFIER,
)


class TestRequiredColumnsValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_unexpected_sheet(self):
        with get_spreadsheet(self.get_path('unexpected_sheet_case_upload', 'xlsx')) as spreadsheet:
            errors = RequiredColumnsValidator.run(spreadsheet)
        self.assertEqual(
            errors,
            ['Unexpected sheet uploaded. Either Rch_id or admission_id should be present']
        )

    def test_validate_required_columns(self):
        with get_spreadsheet(self.get_path('missing_columns_rch_case_upload', 'xlsx')) as spreadsheet:
            errors = RequiredColumnsValidator.run(spreadsheet)
        # extract missing columns from message
        missing_columns = set(errors[0].removeprefix('Missing columns ').split(', '))
        expected_missing_columns = set(REQUIRED_COLUMNS)
        self.assertEqual(
            missing_columns,
            expected_missing_columns
        )

        with get_spreadsheet(self.get_path('missing_columns_sncu_case_upload', 'xlsx')) as spreadsheet:
            errors = RequiredColumnsValidator.run(spreadsheet)
        # extract missing columns from message
        missing_columns = set(errors[0].removeprefix('Missing columns ').split(', '))
        expected_missing_columns = set(REQUIRED_COLUMNS)
        expected_missing_columns.add(NEWBORN_WEIGHT_COLUMN)
        self.assertEqual(
            missing_columns,
            expected_missing_columns
        )


class TestCallColumnsValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_validate_call_columns(self):
        with get_spreadsheet(self.get_path('missing_call_columns_case_upload', 'xlsx')) as spreadsheet:
            errors = CallColumnsValidator.run(spreadsheet)
        self.assertEqual(
            errors[0],
            'Need at least one Call column for Calls 1-6'
        )


class TestRequiredValueValidator(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def _assert_missing_values_for_sheet(self, spreadsheet_name, required_values):
        with get_spreadsheet(self.get_path(spreadsheet_name, 'xlsx')) as spreadsheet:
            for row_num, raw_row in enumerate(spreadsheet.iter_row_dicts()):
                if row_num == 0:
                    continue  # skip first row (header row)
                fields_to_update = raw_row.copy()
                if RCH_BENEFICIARY_IDENTIFIER in fields_to_update:
                    fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
                elif SNCU_BENEFICIARY_IDENTIFIER in fields_to_update:
                    fields_to_update['external_id'] = fields_to_update.pop(SNCU_BENEFICIARY_IDENTIFIER)
                fields_to_update, errors = RequiredValueValidator(
                    row_num=row_num, raw_row=raw_row, fields_to_update=fields_to_update).run()
                self.assertEqual(
                    [error.title for error in errors],
                    ['Missing required column(s)']
                )
                self.assertEqual(
                    [error.message for error in errors],
                    [f"Required columns are {', '.join(required_values)}"]
                )

    def test_validate_required_values(self):
        required_values = ['name', 'MobileNo', 'DIST_NAME', 'Health_Block', 'owner_name',
                           'external_id']
        self._assert_missing_values_for_sheet('missing_values_rch_case_upload', required_values)

        required_values = ['name', 'MobileNo', 'DIST_NAME', 'Health_Block',
                           'owner_name', 'newborn_weight', 'external_id']
        self._assert_missing_values_for_sheet('missing_values_sncu_case_upload', required_values)


class TestCallValidator(SimpleTestCase):
    def test_missing_call_column(self):
        raw_row = _sample_valid_rch_upload()
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
        fields_to_update.pop('Call1')
        row_num = 1

        fields_to_update, errors = CallValidator(raw_row=raw_row, fields_to_update=fields_to_update).run()

        self.assertEqual(
            [error.title for error in errors],
            ['Missing call values']
        )

    def test_invalid_call_value(self):
        raw_row = _sample_valid_rch_upload()
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
        fields_to_update['Call1'] = 'abc'

        fields_to_update, errors = CallValidator(raw_row=raw_row, fields_to_update=fields_to_update).run()

        self.assertEqual(
            [error.title for error in errors],
            ['Latest call value not a date']
        )

    def test_call_value_not_in_last_month(self):
        raw_row = _sample_valid_rch_upload()
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)

        fields_to_update, errors = CallValidator(raw_row=raw_row, fields_to_update=fields_to_update).run()

        self.assertListEqual(
            [error.title for error in errors],
            ['Latest call not in last month']
        )

    def test_skipping_call_validator(self):
        raw_row = _sample_valid_rch_upload()
        raw_row[SKIP_CALL_VALIDATOR] = SKIP_CALL_VALIDATOR_YES
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)

        fields_to_update, errors = CallValidator(raw_row=raw_row, fields_to_update=fields_to_update).run()
        self.assertListEqual(
            [error.title for error in errors],
            []
        )

    def test_skipping_call_validator_unexpected_value(self):
        raw_row = _sample_valid_rch_upload()
        raw_row[SKIP_CALL_VALIDATOR] = 'yup'
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)

        fields_to_update, errors = CallValidator(raw_row=raw_row, fields_to_update=fields_to_update).run()
        self.assertListEqual(
            [error.title for error in errors],
            ['Unexpected value for skipping call validator column']
        )


class TestFormatValidator(SimpleTestCase):
    def test_mobile_number(self):
        raw_row = _sample_valid_rch_upload()
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
        fields_to_update['MobileNo'] = '99'

        fields_to_update, errors = FormatValidator(fields_to_update=fields_to_update).run()

        self.assertEqual(
            [error.title for error in errors],
            ['Mobile number should be 10 digits']
        )


class TestUploadLimitValidator(TestCase):

    def setUp(self):
        super(TestUploadLimitValidator, self).setUp()
        self.domain = Domain(name="test_domain")
        self.domain.save()

    def tearDown(self):
        self.domain.delete()
        super(TestUploadLimitValidator, self).tearDown()

    def test_update_counter(self):
        raw_row = _sample_valid_rch_upload()
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
        row_num = 1
        import_context = {}

        fields_to_update, errors = UploadLimitValidator(
            fields_to_update=fields_to_update, import_context=import_context, domain="test_domain").run()

        self.assertEqual(
            import_context['counter']['watson']['Call1'],
            1
        )
        self.assertEqual(len(errors), 0)

    def test_upload_limit(self):
        raw_row = _sample_valid_rch_upload()
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
        # initialize context to replicate limit reached
        import_context = {'counter': {fields_to_update[OWNER_NAME]: {
            'Call1': OperatorCallLimitSettings.CALL_LIMIT_DEFAULT}}}

        fields_to_update, errors = UploadLimitValidator(
            fields_to_update=fields_to_update, import_context=import_context, domain="test_domain").run()

        self.assertEqual(
            [error.title for error in errors],
            ['Upload limit reached for owner and call type']
        )

    def test_missing_call_column(self):
        raw_row = _sample_valid_rch_upload()
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
        fields_to_update.pop('Call1')
        fields_to_update.pop(OWNER_NAME)
        row_num = 1

        fields_to_update, errors = UploadLimitValidator(
            fields_to_update=fields_to_update, domain="test_domain").run()

        self.assertEqual(
            [error.title for error in errors],
            ['Missing owner name', 'Missing call values']
        )


class TestSuccessfulUpload(TestCase):

    def setUp(self):
        super(TestSuccessfulUpload, self).setUp()
        self.domain = Domain(name="test_domain")
        self.domain.save()

    def tearDown(self):
        self.domain.delete()
        super(TestSuccessfulUpload, self).tearDown()

    def test_successful_upload(self):
        raw_row = _sample_valid_rch_upload()
        raw_row['Call1'] = str(datetime.date.today() - relativedelta(months=1))
        fields_to_update = raw_row.copy()
        fields_to_update['external_id'] = fields_to_update.pop(RCH_BENEFICIARY_IDENTIFIER)
        row_num = 1
        fields_to_update, all_errors = samveg_case_upload_row_operations(
            "test_domain", row_num, raw_row, fields_to_update, {})
        self.assertListEqual(all_errors, [])


def _sample_valid_rch_upload():
    return {
        'Rch_id': 98765,
        'name': 'Sherlock',
        'MobileNo': 9999999999,
        'DIST_NAME': 'USA',
        'Health_Block': 'DC',
        'owner_name': 'watson',
        'Call1': '2021-10-29'
    }
