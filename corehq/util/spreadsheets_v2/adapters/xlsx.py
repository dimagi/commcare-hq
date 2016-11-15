from contextlib import contextmanager
from zipfile import BadZipfile
import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from corehq.util.spreadsheets_v2 import Worksheet, Cell, Workbook, SpreadsheetFileError


@contextmanager
def open_xlsx_workbook(filename):
    with open(filename) as f:
        try:
            openpyxl_workbook = openpyxl.load_workbook(
                f, read_only=True, use_iterators=True, data_only=True)
        except (BadZipfile, InvalidFileException) as e:
            raise SpreadsheetFileError(e.message)
        yield _XLSXWorkbookAdaptor(openpyxl_workbook).to_workbook()


class _XLSXWorksheetAdaptor(object):
    def __init__(self, openpyxl_worksheet):
        self._worksheet = openpyxl_worksheet

    def iter_rows(self):
        for row in self._worksheet.iter_rows():
            yield [Cell(cell.value) for cell in row]

    def to_worksheet(self):
        return Worksheet(title=self._worksheet.title, iter_rows=self.iter_rows)


class _XLSXWorkbookAdaptor(object):

    def __init__(self, openpyxl_workbook):
        self._workbook = openpyxl_workbook

    def to_workbook(self):
        return Workbook(
            worksheets=[_XLSXWorksheetAdaptor(worksheet).to_worksheet()
                        for worksheet in self._workbook.worksheets]
        )
