from __future__ import absolute_import
from contextlib import contextmanager
from zipfile import BadZipfile
from datetime import datetime, time
import openpyxl
from openpyxl.utils.datetime import from_excel
from openpyxl.utils.exceptions import InvalidFileException
from corehq.util.workbook_reading import Worksheet, Cell, Workbook, \
    SpreadsheetFileNotFound, SpreadsheetFileInvalidError, SpreadsheetFileEncrypted

# Got this from running hexdump and then googling
# which matched something on https://en.wikipedia.org/wiki/List_of_file_signatures:
#     Compound File Binary Format,
#     a container format used for document by older versions of Microsoft Office.
#     It is however an open format used by other programs as well.
# Also checked that it's not used non-encrypted xlsx files, which are just .zip files
XLSX_ENCRYPTED_MARKER = '\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'


@contextmanager
def open_xlsx_workbook(filename):
    try:
        f = open(filename)
    except IOError as e:
        raise SpreadsheetFileNotFound(e.message)

    with f as f:
        try:
            openpyxl_workbook = openpyxl.load_workbook(f, read_only=True, data_only=True)
        except InvalidFileException as e:
            raise SpreadsheetFileInvalidError(e.message)
        except BadZipfile as e:
            f.seek(0)
            if f.read(8) == XLSX_ENCRYPTED_MARKER:
                raise SpreadsheetFileEncrypted(u'Workbook is encrypted')
            else:
                raise SpreadsheetFileInvalidError(e.message)
        yield _XLSXWorkbookAdaptor(openpyxl_workbook).to_workbook()


class _XLSXWorksheetAdaptor(object):
    def __init__(self, openpyxl_worksheet):
        self._worksheet = openpyxl_worksheet

    def _make_cell_value(self, cell):
        if isinstance(cell.value, datetime):
            if cell._value == 0 and from_excel(0) == datetime(1899, 12, 30, 0, 0):
                # openpyxl has a bug that treats '12:00:00 AM'
                # as 0 seconds from the 'Windows Epoch' of 1899-12-30
                return time(0, 0)
            elif cell.value.time() == time(0, 0):
                return cell.value.date()
            else:
                return cell.value
        return cell.value

    def iter_rows(self):
        for row in self._worksheet.iter_rows():
            yield [Cell(self._make_cell_value(cell)) for cell in row]

    def to_worksheet(self):
        return Worksheet(title=self._worksheet.title, max_row=self._worksheet.max_row,
                         iter_rows=self.iter_rows)


class _XLSXWorkbookAdaptor(object):

    def __init__(self, openpyxl_workbook):
        self._workbook = openpyxl_workbook

    def to_workbook(self):
        return Workbook(
            worksheets=[_XLSXWorksheetAdaptor(worksheet).to_worksheet()
                        for worksheet in self._workbook.worksheets]
        )
