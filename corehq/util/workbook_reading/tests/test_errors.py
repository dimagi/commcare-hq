from django.test import SimpleTestCase

from corehq.util.workbook_reading import SpreadsheetFileNotFound, SpreadsheetFileInvalidError, \
    SpreadsheetFileExtError, open_any_workbook, SpreadsheetFileEncrypted
from corehq.util.workbook_reading.tests.utils import (
    get_file,
    run_on_all_adapters,
    run_on_all_adapters_except_csv,
    run_on_csv_adapter,
)


class SpreadsheetErrorsTest(SimpleTestCase):
    def test_file_ext(self):
        with self.assertRaises(SpreadsheetFileExtError) as cxt:
            with open_any_workbook(get_file('badext', 'ext')):
                pass
        expected_error = (
            r'File .*/ext/badext.ext does not have a valid extension. Valid '
            'extensions are: csv, xls, xlsx'
        )
        self.assertRegex(str(cxt.exception), expected_error)


@run_on_all_adapters(SpreadsheetErrorsTest)
def test_file_not_found(self, open_workbook, ext):
    with self.assertRaises(SpreadsheetFileNotFound):
        with open_workbook(get_file('nosuchfile', ext)):
            pass


@run_on_all_adapters(SpreadsheetErrorsTest)
def test_empty_file(self, open_workbook, ext):
    with self.assertRaises(SpreadsheetFileInvalidError):
        with open_workbook(get_file('empty_file', ext)):
            pass


@run_on_csv_adapter(SpreadsheetErrorsTest)
def test_csv_file_encrypted(self, open_workbook, ext):
    """An encrypted CSV file raises a SpreadsheetFileInvalidError error."""
    with self.assertRaises(SpreadsheetFileInvalidError):
        with open_workbook(get_file('encrypted', ext)):
            pass


@run_on_csv_adapter(SpreadsheetErrorsTest)
def test_mismatched_row_lengths(self, open_workbook, ext):
    with self.assertRaises(SpreadsheetFileInvalidError):
        with open_workbook(get_file('mixed', ext)):
            pass


@run_on_all_adapters_except_csv(SpreadsheetErrorsTest)
def test_file_encrypted(self, open_workbook, ext):
    with self.assertRaises(SpreadsheetFileEncrypted) as cxt:
        with open_workbook(get_file('encrypted', ext)):
            pass
    self.assertEqual(str(cxt.exception), 'Workbook is encrypted')
