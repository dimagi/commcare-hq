from __future__ import absolute_import
from datetime import datetime, date, time
from django.test import SimpleTestCase
from corehq.util.workbook_reading import (
    Workbook,
    Worksheet,
    make_worksheet,
)
from corehq.util.workbook_reading.tests.utils import get_file, run_on_all_adapters
from corehq.util.test_utils import make_make_path
from six.moves import zip_longest


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


@run_on_all_adapters(SpreadsheetCellTypeTest)
def test_xlsx_types(self, open_workbook, ext):
    with open_workbook(get_file('types', ext)) as workbook:
        self.assert_workbooks_equal(
            workbook,
            Workbook(
                worksheets=[
                    make_worksheet(title='Sheet1', rows=[
                        [u'String', u'Danny'],
                        [u'Date', date(1988, 7, 7)],
                        [u'Date Time', datetime(2016, 1, 1, 12, 0)],
                        [u'Time', time(12, 0)],
                        [u'Midnight', time(0, 0)],
                        [u'Int', 28],
                        [u'Int.0', 5],
                        [u'Float', 5.1],
                        [u'Bool-F', False],
                        [u'Bool-T', True],
                        [u'Empty', None],
                        [u'Percent', 0.49],
                        [u'Calculation', 2],
                        [u'Styled', u'Styled'],
                        [u'Empty Date', None],
                    ]),
                ]
            )
        )
