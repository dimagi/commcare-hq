from __future__ import absolute_import, unicode_literals

from contextlib import contextmanager
from datetime import date, datetime, time

import six
import xlrd
from six.moves import range

from corehq.util.workbook_reading import (
    Cell,
    CellValueError,
    SpreadsheetFileEncrypted,
    SpreadsheetFileInvalidError,
    SpreadsheetFileNotFound,
    Workbook,
    Worksheet,
)


@contextmanager
def open_xls_workbook(filename):
    try:
        with xlrd.open_workbook(filename) as xlrd_workbook:
            yield _XLSWorkbookAdaptor(xlrd_workbook).to_workbook()
    except xlrd.XLRDError as e:
        if six.text_type(e) == 'Workbook is encrypted':
            raise SpreadsheetFileEncrypted(six.text_type(e))
        else:
            raise SpreadsheetFileInvalidError(six.text_type(e))
    except xlrd.compdoc.CompDocError as e:
        raise SpreadsheetFileInvalidError(six.text_type(e))
    except IOError as e:
        raise SpreadsheetFileNotFound(six.text_type(e))


class _XLSWorksheetAdaptor(object):
    def __init__(self, xlrd_sheet):
        self._sheet = xlrd_sheet

    def _make_cell_value(self, cell):
        if cell.ctype == xlrd.XL_CELL_NUMBER:
            # cell.value is a float, return int if it's an int
            if int(cell.value) == cell.value:
                return int(cell.value)
            else:
                return cell.value
        elif cell.ctype == xlrd.XL_CELL_DATE:
            try:
                datetime_tuple = xlrd.xldate_as_tuple(cell.value, self._sheet.book.datemode)
            except xlrd.XLDateError as e:
                # https://xlrd.readthedocs.io/en/latest/dates.html
                raise CellValueError("Error interpreting spreadsheet value '{}' as date: {}"
                                     .format(cell.value, repr(e)))
            if datetime_tuple[:3] == (0, 0, 0):
                return time(*datetime_tuple[3:])
            elif datetime_tuple[3:] == (0, 0, 0):
                return date(*datetime_tuple[:3])
            else:
                return datetime(*datetime_tuple)
        elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
            return bool(cell.value)
        elif cell.ctype == xlrd.XL_CELL_EMPTY:
            return None
        else:
            return cell.value

    def iter_rows(self):
        for i in range(self._sheet.nrows):
            yield [Cell(self._make_cell_value(cell)) for cell in self._sheet.row(i)]

    def to_worksheet(self):
        return Worksheet(title=self._sheet.name, max_row=self._sheet.nrows,
                         iter_rows=self.iter_rows)


class _XLSWorkbookAdaptor(object):

    def __init__(self, xlrd_workbook):
        self._book = xlrd_workbook

    def to_workbook(self):
        return Workbook(
            worksheets=[_XLSWorksheetAdaptor(worksheet).to_worksheet()
                        for worksheet in self._book.sheets()]
        )
