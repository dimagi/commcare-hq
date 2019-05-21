class SpreadsheetFileError(Exception):
    pass


class SpreadsheetFileExtError(SpreadsheetFileError):
    pass


class SpreadsheetFileInvalidError(SpreadsheetFileError):
    pass


class SpreadsheetFileNotFound(SpreadsheetFileError, IOError):
    pass


class SpreadsheetFileEncrypted(SpreadsheetFileError):
    pass


class CellValueError(Exception):
    pass
