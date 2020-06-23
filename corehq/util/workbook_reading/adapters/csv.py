import ast
from contextlib import contextmanager
import datetime
from dateutil.parser import parse
import csv
import os

from corehq.util.workbook_reading import (
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
    except (UnicodeDecodeError, csv.Error) as error:
        # Rather than trying to determine why the file is not readable (invalid
        # characters, file is encrypted, etc.), just raise an error that the file
        # is not readable.
        raise SpreadsheetFileInvalidError(str(error))
    except IOError as error:
        raise SpreadsheetFileNotFound(str(error))
    except FileNotFoundError as error:
        raise SpreadsheetFileNotFound(str(error))


def format_value(str_value):
    """Attempt to format a str_value into its type."""
    # Try to see if the str_value is a empty.
    if str_value == "":
        return None

    # Try to see if the str_value is a number (float or integer).
    try:
        number = ast.literal_eval(str_value)
        if int(number) == float(number):
            return int(number)
        else:
            return float(number)
    except (SyntaxError, ValueError):
        pass

    # Try to see if the str_value is a date or a time.
    try:
        parsed_datetime = parse(str_value)
        # Because dateutil.parser.parse always returns a datetime, we do some guessing
        # for whether the value is a datetime, a date, or a time.
        today_midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_date = today_midnight.date()
        # If the parsed_datetime time is midnight, then check if the user indicated
        # midnight or not.
        if parsed_datetime.time() == today_midnight.time():
            if ("am" in str_value.lower() or "00:00" in str_value):
                # The user has indicated to use midnight.
                # If the str_value is long, then this must be a datetime.
                if len(str_value) > 10:
                    return parsed_datetime
                else:
                    # The str_value is short, so this must be a time.
                    return parsed_datetime.time()
            else:
                # The user has not indicated to use midnight, so this must be a date.
                return parsed_datetime.date()
        elif parsed_datetime.date() == today_date:
            # We have already handled the case that the user specified a date (but
            # not a time), so parsed_datetime is a datetime with a time of midnight.
            # If the parsed_datetime has a date of today, but a time of not midnight,
            # then either the user specified both the date and the time (meaning
            # we should return the datetime), or the user specified only the time (so
            # we should return only the time).

            # If the str_value is long, then this must be a datetime.
            if len(str_value) > 10:
                return parsed_datetime
            else:
                # The str_value is short, so this must be a time.
                return parsed_datetime.time()
        else:
            # Otherwise, this must be a datetime.
            return parsed_datetime
    except ValueError:
        pass

    # Try to see if the str_value is a boolean.
    if str_value.lower() in ["true", "t", "yes", "y"]:
        return True
    elif str_value.lower() in ["false", "f", "no", "n"]:
        return False

    # Try to see if the str_value is a percent.
    if "%" in str_value:
        try:
            return float(str_value.replace("%", "")) / 100
        except ValueError:
            pass

    return str_value


class _CSVWorkbookAdaptor(object):

    def __init__(self, csv_file):
        self._file = csv_file

    def to_workbook(self):
        rows = []

        # Loop through the rows, and change any string to its appropriate type.
        for row in csv.reader(self._file, delimiter=","):
            formatted_row = []
            for column in row:
                formatted_row.append(format_value(column))
            rows.append(formatted_row)

        return Workbook(worksheets=[make_worksheet(rows, title='Sheet1')])
