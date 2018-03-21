from __future__ import absolute_import
from __future__ import unicode_literals
import xlrd


class ImporterError(Exception):
    """
    Generic error raised for any problem to do with finding, opening, reading, etc.
    the file being imported

    When possible, a more specific subclass should be used
    """


class ImporterFileNotFound(ImporterError):
    """Raised when a referenced file can't be found"""


class ImporterRefError(ImporterError):
    """Raised when a Soil download ref is None"""


class ImporterExcelError(ImporterError, xlrd.XLRDError):
    """
    Generic error raised for any error parsing an Excel file

    When possible, a more specific subclass should be used
    """


class ImporterExcelFileEncrypted(ImporterExcelError):
    """Raised when a file cannot be open because it is encrypted (password-protected)"""


class InvalidCustomFieldNameException(Exception):
    """Raised when a custom field name is reserved (e.g. "type")"""
    pass


class InvalidImportValueException(Exception):

    def __init__(self, column=None):
        self.column = column


class InvalidDateException(InvalidImportValueException):
    pass


class InvalidIntegerException(InvalidImportValueException):
    pass
