from contextlib import contextmanager
from corehq.util.workbook_reading import SpreadsheetFileExtError
from .xls import open_xls_workbook
from .xlsx import open_xlsx_workbook


@contextmanager
def open_any_workbook(filename):
    if filename.endswith('.xls'):
        with open_xls_workbook(filename) as workbook:
            yield workbook
    elif filename.endswith('.xlsx'):
        with open_xlsx_workbook(filename) as workbook:
            yield workbook
    else:
        raise SpreadsheetFileExtError('File {} does not end in .xls or .xlsx'
                                      .format(filename))
