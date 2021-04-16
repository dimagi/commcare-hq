from datetime import date, datetime, time
from itertools import zip_longest

from django.test import SimpleTestCase

from corehq.util.test_utils import make_make_path
from corehq.util.workbook_reading import Workbook, Worksheet, make_worksheet
from corehq.util.workbook_reading.tests.utils import (
    get_file,
    run_on_all_adapters_except_csv,
    run_on_csv_adapter,
)

_make_path = make_make_path(__file__)


class SpreadsheetCellTypeTest(SimpleTestCase):

    def assert_workbooks_equal(self, workbook1, workbook2):
        fillvalue = Exception('Worksheet missing')

        self.assertEqual(workbook1._replace(worksheets=None),
                         workbook2._replace(worksheets=None))
        for worksheet1, worksheet2 in zip_longest(
                workbook1.worksheets, workbook2.worksheets, fillvalue=fillvalue):
            self._assert_worksheets_equal(worksheet1, worksheet2)

    def _assert_worksheets_equal(self, worksheet1, worksheet2):
        fillvalue = Exception('Row missing')
        self.assertIsInstance(worksheet1, Worksheet)
        self.assertIsInstance(worksheet2, Worksheet)
        self.assertEqual(worksheet1._replace(iter_rows=None),
                         worksheet2._replace(iter_rows=None))
        for self_row, other_row in zip_longest(
                worksheet1.iter_rows(), worksheet2.iter_rows(), fillvalue=fillvalue):
            self.assertEqual(self_row, other_row)


@run_on_all_adapters_except_csv(SpreadsheetCellTypeTest)
def test_xlsx_types(self, open_workbook, ext):
    with open_workbook(get_file('types', ext)) as workbook:
        self.assert_workbooks_equal(
            workbook,
            Workbook(
                worksheets=[
                    make_worksheet(title='Sheet1', rows=[
                        ['String', 'Danny'],
                        ['Date', date(1988, 7, 7)],
                        ['Date Time', datetime(2016, 1, 1, 12, 0)],
                        ['Time', time(12, 0)],
                        ['Midnight', date(1899, 12, 30) if ext == 'xlsx' else time(0, 0)],
                        ['Int', 28],
                        ['Int.0', 5],
                        ['Float', 5.1],
                        ['Bool-F', False],
                        ['Bool-T', True],
                        ['Empty', None],
                        ['Percent', 0.49],
                        ['Calculation', 2],
                        ['Styled', 'Styled'],
                        ['Empty Date', None],
                    ]),
                ]
            )
        )


@run_on_csv_adapter(SpreadsheetCellTypeTest)
def test_csv_types(self, open_workbook, ext):
    with open_workbook(get_file('types', ext)) as workbook:
        self.assert_workbooks_equal(
            workbook,
            Workbook(
                worksheets=[
                    make_worksheet(title='Sheet1', rows=[
                        ['String', 'Danny'],
                        ['Date', '7/7/1988'],
                        ['Date Time', '1/1/2016 12:00'],
                        ['Time', '12:00 PM'],
                        ['Midnight', '12:00 AM'],
                        ['Int', '28'],
                        ['Int.0', '5.0'],
                        ['Float', '5.1'],
                        ['Bool-F', 'FALSE'],
                        ['Bool-T', 'TRUE'],
                        ['Empty', ''],
                        ['Percent', '49%'],
                        ['Calculation', '2'],
                        ['Styled', 'Sطαйλד tэξţ'],
                        ['Empty Date', ''],
                    ]),
                ]
            )
        )
