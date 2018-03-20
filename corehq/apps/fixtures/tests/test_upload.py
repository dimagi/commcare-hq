from __future__ import absolute_import
from __future__ import unicode_literals
import tempfile

from couchexport.export import export_raw
from couchexport.models import Format
from django.test import SimpleTestCase, TestCase
from io import BytesIO

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.fixtures.upload import validate_fixture_file_format
from corehq.apps.fixtures.upload.failure_messages import FAILURE_MESSAGES
from corehq.apps.fixtures.upload.run_upload import _run_fixture_upload
from corehq.apps.fixtures.upload.workbook import get_workbook
from corehq.util.test_utils import make_make_path
from corehq.util.test_utils import generate_cases


_make_path = make_make_path(__file__)


validation_test_cases = [
    ('duplicate_tag', [
        "Lookup-tables should have unique 'table_id'. "
        "There are two rows with table_id 'things' in 'types' sheet.",

    ]),
    ('multiple_errors', [
        "Excel-sheet 'level_1' does not contain the column "
        "'field: fun_fact' as specified in its 'types' definition",
        "Excel-sheet 'level_1' does not contain the column "
        "'field: other' as specified in its 'types' definition",
        "Excel-sheet 'level_2' does not contain the column "
        "'field: other' as specified in its 'types' definition",
        "There's no sheet for type 'level_3' in 'types' sheet. "
        "There must be one sheet per row in the 'types' sheet.",
    ]),
    ('type_has_no_sheet', [
        "There's no sheet for type 'things' in 'types' sheet. "
        "There must be one sheet per row in the 'types' sheet.",
    ]),
    ('has_no_field_column', [
        "Excel-sheet 'things' does not contain the column 'field: name' "
        "as specified in its 'types' definition",
    ]),
    ('has_extra_column', [
        "Excel-sheet 'things' has an extra column"
        "'field: fun_fact' that's not defined in its 'types' definition",
    ]),
    ('sheet_has_no_property', [
        "Excel-sheet 'things' does not contain property "
        "'lang' of the field 'name' as specified in its 'types' definition",
    ]),
    ('sheet_has_extra_property', [
        "Excel-sheet 'things' has an extra property "
        "'style' for the field 'name' that's not defined in its 'types' definition. "
        "Re-check the formatting",
    ]),
    ('invalid_field_with_property', [
        "Fields with attributes should be numbered as 'field: name integer'",
        # also triggers wrong_field_property_combos
        "Number of values for field 'name' and attribute 'lang' should be same",
    ]),
    ('invalid_property', [
        "Attribute should be written as 'name: lang integer'",
        # also triggers wrong_field_property_combos
        "Number of values for field 'name' and attribute 'lang' should be same",
    ]),
    ('wrong_field_property_combos', [
        "Number of values for field 'name' and attribute 'lang' should be same",
    ]),
    ('has_no_column', [
        "Workbook 'types' has no column 'table_id'.",
    ]),
    ('neither_fields_nor_attributes', [
        "Lookup-tables can not have empty fields and empty properties on items. "
        "table_id 'things' has no fields and no properties",
    ]),
    ('invalid_field_syntax', [
        "In excel-sheet 'things', field 'name' should be numbered as 'field: name integer",
    ]),
    ('wrong_property_syntax', [
        "Properties should be specified as 'field 1: property 1'. In 'types' sheet, "
        "'field 1' is not correctly formatted"
    ]),
    ('invalid_field_name_numerical', [
        "Error in 'types' sheet for 'field 1', '100'. "
        "Field names should be strings, not numbers",
    ]),
    ('not_excel_file', [
        "Invalid file-format. Please upload a valid xlsx file.",
    ]),
    ('no_types_sheet', [
        "Workbook does not contain a sheet called types",
    ]),
    ('wrong_index_syntax', [
        "'field 1' is not correctly formatted in 'types' sheet. Whether a field is indexed should be specified "
        "as 'field 1: is_indexed?'. Its value should be 'yes' or 'no'.",
    ]),
    ('field_type_error', [
        "Fields with attributes should be numbered as 'field: name integer'"
    ]),
    ('property_type_error', [
        "Attribute should be written as 'name: lang integer'"
    ])
]


@generate_cases(
    validation_test_cases
)
def test_validation(self, filename, error_messages):
    upload_file = _make_path('test_upload', '{}.xlsx'.format(filename))
    if error_messages:
        with self.assertRaises(FixtureUploadError) as context:
            validate_fixture_file_format(upload_file)
        self.assertEqual(context.exception.errors, error_messages)
    else:
        # assert doesn't raise anything
        validate_fixture_file_format(upload_file)


class TestValidationComprehensiveness(SimpleTestCase):
    maxDiff = None

    def test_comprehensiveness(self):
        to_test = set(FAILURE_MESSAGES.keys())
        tested = set([validation for validation, _ in validation_test_cases])
        untested = to_test - tested
        self.assert_(
            not untested,
            "Some fixture upload errors are still untested.\n\n"
            "You have to write a test for the following fixture upload errors:\n{}"
            .format('\n'.join(untested)))


class TestFixtureUpload(TestCase):

    headers = (
        (
            'types',
            ('Delete(Y/N)', 'table_id', 'is_global?', 'field 1', 'field 1: is_indexed?')
        ),
        (
            'things',
            ('UID', 'Delete(Y/N)', 'field: name')
        )
    )

    @staticmethod
    def make_rows(item_rows):
        # given a list of fixture-items, return formatted excel rows
        return (
            (
                'types',
                ('N', 'things', 'yes', 'name', 'yes')
            ),
            (
                'things',
                tuple(item_rows)
            )
        )

    @classmethod
    def setUpClass(cls):
        super(TestFixtureUpload, cls).setUpClass()
        cls.domain = 'fixture-upload-test'
        cls.project = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestFixtureUpload, cls).tearDownClass()

    def _get_workbook(self, filename):
        return get_workbook(_make_path('test_upload', '{}.xlsx'.format(filename)))

    def _get_workbook_from_data(self, headers, rows):
        file = BytesIO()
        export_raw(headers, rows, file, format=Format.XLS_2007)
        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            return get_workbook(f)

    def get_fixture_items(self, attribute):
        # return list of 'attribute' values of fixture table 'things'
        fixtures = []
        for fixture in FixtureDataItem.get_item_list(self.domain, 'things'):
            fixtures.append(fixture.fields.get(attribute).field_list[0].field_value)
        return fixtures

    def test_indexed_field(self):
        # test indexed fields are ready correctly
        workbook = self._get_workbook('ok')
        type_sheets = workbook.get_all_type_sheets()
        indexed_field = type_sheets[0].fields[0]
        self.assertEqual(indexed_field.field_name, 'name')
        self.assertTrue(indexed_field.is_indexed)

    def test_row_addition(self):
        # upload and then reupload with addition of a new fixture-item should create new items

        initial_rows = [(None, 'N', 'apple')]
        rows = self.make_rows(initial_rows)
        workbook = self._get_workbook_from_data(self.headers, rows)
        _run_fixture_upload(self.domain, workbook)

        self.assertListEqual(
            self.get_fixture_items('name'),
            ['apple']
        )

        # reupload with additional row
        apple_id = FixtureDataItem.get_item_list(self.domain, 'things')[0]._id
        new_rows = [(apple_id, 'N', 'apple'), (None, 'N', 'orange')]
        workbook = self._get_workbook_from_data(self.headers, self.make_rows(new_rows))
        _run_fixture_upload(self.domain, workbook)
        self.assertItemsEqual(
            self.get_fixture_items('name'),
            ['apple', 'orange']
        )
