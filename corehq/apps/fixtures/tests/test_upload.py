from django.test import SimpleTestCase
from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.upload import validate_fixture_file_format
from corehq.apps.fixtures.upload.failure_messages import FAILURE_MESSAGES
from corehq.apps.fixtures.upload.workbook import get_workbook
from corehq.util.test_utils import make_make_path
from corehq.util.test_utils import generate_cases


_make_path = make_make_path(__file__)


validation_test_cases = [
    ('duplicate_tag', [
        u"Lookup-tables should have unique 'table_id'. "
        u"There are two rows with table_id 'things' in 'types' sheet.",

    ]),
    ('multiple_errors', [
        u"Excel-sheet 'level_1' does not contain the column "
        u"'field: fun_fact' as specified in its 'types' definition",
        u"Excel-sheet 'level_1' does not contain the column "
        u"'field: other' as specified in its 'types' definition",
        u"Excel-sheet 'level_2' does not contain the column "
        u"'field: other' as specified in its 'types' definition",
        u"There's no sheet for type 'level_3' in 'types' sheet. "
        u"There must be one sheet per row in the 'types' sheet.",
    ]),
    ('type_has_no_sheet', [
        u"There's no sheet for type 'things' in 'types' sheet. "
        u"There must be one sheet per row in the 'types' sheet.",
    ]),
    ('has_no_field_column', [
        u"Excel-sheet 'things' does not contain the column 'field: name' "
        u"as specified in its 'types' definition",
    ]),
    ('has_extra_column', [
        u"Excel-sheet 'things' has an extra column"
        u"'field: fun_fact' that's not defined in its 'types' definition",
    ]),
    ('sheet_has_no_property', [
        u"Excel-sheet 'things' does not contain property "
        u"'lang' of the field 'name' as specified in its 'types' definition",
    ]),
    ('sheet_has_extra_property', [
        u"Excel-sheet 'things' has an extra property "
        u"'style' for the field 'name' that's not defined in its 'types' definition. "
        u"Re-check the formatting",
    ]),
    ('invalid_field_with_property', [
        u"Fields with attributes should be numbered as 'field: name integer'",
        # also triggers wrong_field_property_combos
        u"Number of values for field 'name' and attribute 'lang' should be same",
    ]),
    ('invalid_property', [
        u"Attribute should be written as 'name: lang integer'",
        # also triggers wrong_field_property_combos
        u"Number of values for field 'name' and attribute 'lang' should be same",
    ]),
    ('wrong_field_property_combos', [
        u"Number of values for field 'name' and attribute 'lang' should be same",
    ]),
    ('has_no_column', [
        u"Workbook 'types' has no column 'table_id'.",
    ]),
    ('neither_fields_nor_attributes', [
        u"Lookup-tables can not have empty fields and empty properties on items. "
        u"table_id 'things' has no fields and no properties",
    ]),
    ('invalid_field_syntax', [
        u"In excel-sheet 'things', field 'name' should be numbered as 'field: name integer",
    ]),
    ('wrong_property_syntax', [
        u"Properties should be specified as 'field 1: property 1'. In 'types' sheet, "
        u"'field 1' is not correctly formatted"
    ]),
    ('invalid_field_name_numerical', [
        u"Error in 'types' sheet for 'field 1', '100'. "
        u"Field names should be strings, not numbers",
    ]),
    ('not_excel_file', [
        u"Invalid file-format. Please upload a valid xlsx file.",
    ]),
    ('no_types_sheet', [
        u"Workbook does not contain a sheet called types",
    ]),
    ('wrong_index_syntax', [
        u"'field 1' is not correctly formatted in 'types' sheet. Whether a field is indexed should be specified "
        "as 'field 1: is_indexed?'. Its value should be 'yes' or 'no'.",
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


class TestFixtureUpload(SimpleTestCase):
    def _get_workbook(self, filename):
        return get_workbook(_make_path('test_upload', '{}.xlsx'.format(filename)))

    def test_indexed_field(self):
        workbook = self._get_workbook('ok')
        type_sheets = workbook.get_all_type_sheets()
        indexed_field = type_sheets[0].fields[0]
        self.assertEqual(indexed_field.field_name, 'name')
        self.assertTrue(indexed_field.is_indexed)
