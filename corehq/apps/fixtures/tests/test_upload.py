from collections import namedtuple
import os
from django.test import SimpleTestCase
from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.upload import FixtureWorkbook


def _make_path(*args):
    return os.path.join(os.path.dirname(__file__), *args)


UploadTestConfig = namedtuple('UploadTestConfig', ['upload_file', 'error_messages'])


def _upload_test(name, error_messages):
    config = UploadTestConfig(_make_path('test_upload', '{}.xlsx'.format(name)),
                              error_messages)

    def inner(self):
        self._test(config)

    inner.func_name = 'test_{}'.format(name)

    return inner


class TestFixtureUpload(SimpleTestCase):
    maxDiff = None

    def _test(self, config):
        wb = FixtureWorkbook(config.upload_file)
        with self.assertRaises(FixtureUploadError) as context:
            wb.validate()
        self.assertEqual(context.exception.errors, config.error_messages)

    test_multiple_errors = _upload_test('multiple_errors', [
        u"Excel-sheet 'level_1' does not contain the column "
        u"'fun_fact' as specified in its 'types' definition",
        u"Excel-sheet 'level_1' does not contain the column "
        u"'other' as specified in its 'types' definition",
        u"Excel-sheet 'level_2' does not contain the column "
        u"'other' as specified in its 'types' definition",
        u"There's no sheet for type 'level_3' in 'types' sheet. "
        u"There must be one sheet per row in the 'types' sheet.",
    ])
    test_type_has_no_sheet = _upload_test('type_has_no_sheet', [
        u"There's no sheet for type 'things' in 'types' sheet. "
        u"There must be one sheet per row in the 'types' sheet.",
    ])
    test_has_no_field_column = _upload_test('has_no_field_column', [
        u"Excel-sheet 'things' does not contain the column 'name' "
        u"as specified in its 'types' definition",
    ])
    test_has_extra_column = _upload_test('has_extra_column', [
        u"Excel-sheet 'things' has an extra column"
        u"'fun_fact' that's not defined in its 'types' definition",
    ])
    test_sheet_has_no_property = _upload_test('sheet_has_no_property', [
        u"Excel-sheet 'things' does not contain property "
        u"'lang' of the field 'name' as specified in its 'types' definition",
    ])
    test_sheet_has_extra_property = _upload_test('sheet_has_extra_property', [
        u"Excel-sheet 'things' has an extra property "
        u"'style' for the field 'name' that's not defined in its 'types' definition. "
        u"Re-check the formatting",
    ])
    test_invalid_field_with_property = _upload_test('invalid_field_with_property', [
        u"Fields with attributes should be numbered as 'field: name integer'",
        # also triggers wrong_field_property_combos
        u"Number of values for field 'name' and attribute 'lang' should be same"
    ])
    test_invalid_property = _upload_test('invalid_property', [
        u"Attribute should be written as 'name: lang integer'",
        # also triggers wrong_field_property_combos
        u"Number of values for field 'name' and attribute 'lang' should be same"
    ])
    test_wrong_field_property_combos = _upload_test('wrong_field_property_combos', [
        u"Number of values for field 'name' and attribute 'lang' should be same"
    ])
