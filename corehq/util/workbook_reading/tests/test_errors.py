from django.test import SimpleTestCase

from corehq.util.workbook_reading import SpreadsheetFileNotFound, SpreadsheetFileInvalidError, \
    SpreadsheetFileExtError, open_any_workbook, SpreadsheetFileEncrypted
from corehq.util.workbook_reading.tests.utils import run_on_all_adapters, get_file


class SpreadsheetErrorsTest(SimpleTestCase):
    def test_file_ext(self):
        with self.assertRaises(SpreadsheetFileExtError) as cxt:
            with open_any_workbook(get_file('badext', 'ext')):
                pass
        self.assertRegex(str(cxt.exception),
                                 r'File .*/ext/badext.ext does not end in .xls or .xlsx')


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


@run_on_all_adapters(SpreadsheetErrorsTest)
def test_file_encrypted(self, open_workbook, ext):
    with self.assertRaises(SpreadsheetFileEncrypted) as cxt:
        with open_workbook(get_file('encrypted', ext)):
            pass
    self.assertEqual(str(cxt.exception), 'Workbook is encrypted')
