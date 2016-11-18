from corehq.apps.case_importer_v1.util import WorksheetWrapper
from corehq.util.spreadsheets_v2 import Worksheet, Cell


def default_row_generator(header_row, index):
    # by default, just return [propertyname-rowid] for every cell
    return [u'{col}-{row}'.format(row=index, col=col) for col in header_row]


def ExcelFileFake(header_columns=None, num_rows=0, row_generator=default_row_generator):

    def iter_rows():
        yield [Cell(value) for value in header_columns]
        for i in range(num_rows):
            yield [Cell(value) for value in row_generator(header_columns, i)]

    return WorksheetWrapper(
        Worksheet(title=None, max_row=1 + num_rows, iter_rows=iter_rows), True)
