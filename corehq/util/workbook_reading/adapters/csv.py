from contextlib import contextmanager
import csv
import os

from corehq.util.workbook_reading import (
    SpreadsheetFileEncrypted,
    SpreadsheetFileInvalidError,
    SpreadsheetFileNotFound,
    Workbook,
)
from .raw_data import make_worksheet


@contextmanager
def open_csv_workbook(filename):
    try:
        if os.stat(filename).st_size <= 1:
            raise SpreadsheetFileInvalidError('File is empty')
        with open(filename, "r") as csv_file:
            yield _CSVWorkbookAdaptor(csv_file).to_workbook()
    except UnicodeDecodeError as error:
        raise SpreadsheetFileEncrypted(str(error))
    except csv.Error as error:
        if str(error) == 'line contains NUL':
            raise SpreadsheetFileEncrypted('Workbook is encrypted')
        else:
            raise SpreadsheetFileInvalidError(str(error))
    except IOError as error:
        raise SpreadsheetFileNotFound(str(error))
    except FileNotFoundError as error:
        raise SpreadsheetFileNotFound(str(error))


class _CSVWorkbookAdaptor(object):

    def __init__(self, csv_file):
        self._file = csv_file

    def to_workbook(self):
        rows = []
        for row in csv.reader(self._file, delimiter=","):
            rows.append(row)

        return Workbook(worksheets=[make_worksheet(rows, title='Sheet1')])
