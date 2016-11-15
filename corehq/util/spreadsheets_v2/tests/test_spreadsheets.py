from datetime import datetime
from itertools import izip_longest
import os
from django.test import SimpleTestCase
from corehq.util.spreadsheets_v2.adapters import open_xlsx_workbook, open_xls_workbook
from corehq.util.spreadsheets_v2.datamodels import Workbook, Worksheet, Cell
from corehq.util.spreadsheets_v2.exceptions import SpreadsheetFileError


def _make_path(*args):
    return os.path.join(os.path.dirname(__file__), *args)


class ExcelCellTypeTest(SimpleTestCase):

    def assert_workbooks_equal(self, workbook1, workbook2):
        fillvalue = object()

        def assert_worksheets_equal(worksheet1, worksheet2):
            self.assertIsInstance(worksheet1, Worksheet)
            self.assertIsInstance(worksheet2, Worksheet)
            self.assertEqual(worksheet1._replace(iter_rows=None),
                             worksheet2._replace(iter_rows=None))
            for self_row, other_row in izip_longest(
                    worksheet1.iter_rows(), worksheet2.iter_rows(), fillvalue=fillvalue):
                self.assertEqual(self_row, other_row)

        self.assertEqual(workbook1._replace(worksheets=None),
                         workbook2._replace(worksheets=None))
        for worksheet1, worksheet2 in izip_longest(
                workbook1.worksheets, workbook2.worksheets, fillvalue=fillvalue):
            assert_worksheets_equal(worksheet1, worksheet2)

    def _test_types(self, filepath, open_workbook):
        with open_workbook(filepath) as workbook:
            self.assert_workbooks_equal(
                workbook,
                Workbook(
                    worksheets=[
                        Worksheet(title='Sheet1', iter_rows=lambda: iter([
                            [Cell(u'Name'), Cell(u'Date of Birth'), Cell(u'Age')],
                            [Cell(u'Danny'), Cell(datetime(1988, 7, 7, 0, 0)), Cell(28)]
                        ]))
                    ]
                )
            )

    def test_xlsx_types(self):
        self._test_types(_make_path('files', 'xlsx', 'types.xlsx'), open_xlsx_workbook)

    def test_xls_types(self):
        self._test_types(_make_path('files', 'xls', 'types.xls'), open_xls_workbook)

    def test_xls_empty_file(self):
        with self.assertRaises(SpreadsheetFileError):
            with open_xls_workbook(_make_path('files', 'xls', 'empty_file.xls')):
                pass

    def test_xlsx_empty_file(self):
        with self.assertRaises(SpreadsheetFileError):
            with open_xlsx_workbook(_make_path('files', 'xlsx', 'empty_file.xlsx')):
                pass
