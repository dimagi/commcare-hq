from __future__ import absolute_import
from corehq.util.workbook_reading import Cell, Worksheet


def make_worksheet(rows=None, title=None):
    rows = rows or []
    row_lengths = [len(row) for row in rows]
    assert all(row_length == row_lengths[0] for row_length in row_lengths), \
        "rows must be all the same length"

    def iter_rows():
        for row in rows:
            yield [Cell(value) for value in row]

    return Worksheet(title=title, max_row=len(rows), iter_rows=iter_rows)
