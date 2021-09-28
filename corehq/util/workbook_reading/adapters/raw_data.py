from corehq.util.workbook_reading import Cell, Worksheet
from corehq.util.workbook_reading.exceptions import SpreadsheetFileInvalidError


def make_worksheet(rows=None, title=None):
    rows = rows or []
    row_lengths = [len(row) for row in rows]
    if any(row_length != row_lengths[0] for row_length in row_lengths):
        raise SpreadsheetFileInvalidError("Rows must be all the same length")

    def iter_rows():
        for row in rows:
            yield [Cell(value) for value in row]

    return Worksheet(title=title, max_row=len(rows), iter_rows=iter_rows)
