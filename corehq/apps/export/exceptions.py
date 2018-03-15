

from __future__ import unicode_literals
class ExportAppException(Exception):
    pass


class BadExportConfiguration(ExportAppException):
    pass


class ExportNotFound(ExportAppException):
    pass


class ExportFormValidationException(Exception):
    pass


class ExportAsyncException(Exception):
    pass


class SkipConversion(Exception):
    """Raised when we need to skip a column during export conversion"""
