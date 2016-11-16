class ExcelFileFake(object):
    """
    Provides the minimal API of ExcelFile used by the importer
    """
    class Workbook(object):

        def __init__(self):
            self._datemode = 0

        @property
        def datemode(self):
            return self._datemode

    def __init__(self, header_columns=None, num_rows=0, has_errors=False, row_generator=None):
        self.header_columns = header_columns or []
        self.num_rows = num_rows
        self.row_generator = row_generator or default_row_generator
        self.workbook = self.Workbook()

    def get_header_columns(self):
        return self.header_columns

    @property
    def max_row(self):
        return self.num_rows

    def iter_rows(self):
        for i in range(self.max_row):
            yield self._get_row(i)

    def _get_row(self, index):
        return self.row_generator(self, index)


def default_row_generator(excel_file, index):
    # by default, just return [propertyname-rowid] for every cell
    return [u'{col}-{row}'.format(row=index, col=col) for col in excel_file.header_columns]
