class HeaderValueError(Exception):
    pass


class InvalidExcelFileException(Exception):
    pass


class JSONReaderError(Exception):
    pass


class StringTypeRequiredError(Exception):
    pass


class UnknownFileRefException(Exception):
    pass


class WorkbookJSONError(Exception):
    pass


class WorkbookTooManyRows(Exception):
    """Workbook row count exceeds MAX_WORKBOOK_ROWS"""

    def __init__(self, max_row_count, actual_row_count):
        super().__init__()
        self.max_row_count = max_row_count
        self.actual_row_count = actual_row_count
