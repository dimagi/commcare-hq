from contextlib import contextmanager
from datetime import datetime
import xlrd
from corehq.util.spreadsheets_v2.datamodels import Worksheet, Cell, Workbook
from corehq.util.spreadsheets_v2.exceptions import SpreadsheetFileError


@contextmanager
def open_xls_workbook(filename):
    try:
        with xlrd.open_workbook(filename) as xlrd_workbook:
            yield _XLSWorkbookAdaptor(xlrd_workbook).to_workbook()
    except xlrd.XLRDError as e:
        raise SpreadsheetFileError(e.message)


class _XLSWorksheetAdaptor(object):
    def __init__(self, xlrd_sheet):
        self._sheet = xlrd_sheet

    def _make_cell_value(self, cell):
        if cell.ctype == xlrd.XL_CELL_NUMBER:
            return int(cell.value)
        elif cell.ctype == xlrd.XL_CELL_DATE:
            return datetime(*xlrd.xldate_as_tuple(cell.value, self._sheet.book.datemode))
        else:
            return cell.value

    def iter_rows(self):
        for i in range(self._sheet.nrows):
            yield [Cell(self._make_cell_value(cell)) for cell in self._sheet.row(i)]

    def to_worksheet(self):
        return Worksheet(title=self._sheet.name, iter_rows=self.iter_rows)


class _XLSWorkbookAdaptor(object):

    def __init__(self, xlrd_workbook):
        self._book = xlrd_workbook

    def to_workbook(self):
        return Workbook(
            worksheets=[_XLSWorksheetAdaptor(worksheet).to_worksheet()
                        for worksheet in self._book.sheets()]
        )
