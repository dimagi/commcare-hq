from contextlib import contextmanager
from corehq.util.workbook_reading import SpreadsheetFileExtError
from .csv import open_csv_workbook
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
    elif filename.endswith('.csv'):
        with open_csv_workbook(filename) as workbook:
            yield workbook
    else:
        raise SpreadsheetFileExtError('File {} does not end in .csv or .xls or .xlsx'
                                      .format(filename))
