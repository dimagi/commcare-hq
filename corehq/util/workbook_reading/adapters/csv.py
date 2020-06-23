from contextlib import contextmanager
import csv
import os

from corehq.util.workbook_reading import (
    SpreadsheetFileInvalidError,
    SpreadsheetFileNotFound,
    Workbook,
)
from .raw_data import make_worksheet
from .utils import format_str_to_its_type


@contextmanager
def open_csv_workbook(filename):
    try:
        if os.stat(filename).st_size <= 1:
            raise SpreadsheetFileInvalidError('File is empty')
        with open(filename, "r") as csv_file:
            yield _CSVWorkbookAdaptor(csv_file).to_workbook()
    except (UnicodeDecodeError, csv.Error) as error:
        # Rather than trying to determine why the file is not readable (invalid
        # characters, file is encrypted, etc.), just raise an error that the file
        # is not readable.
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

        # Loop through the rows, and change any string to its appropriate type.
        for row in csv.reader(self._file, delimiter=","):
            formatted_row = []
            for column in row:
                formatted_row.append(format_str_to_its_type(column))
            rows.append(formatted_row)

        return Workbook(worksheets=[make_worksheet(rows, title='Sheet1')])
