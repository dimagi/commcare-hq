

from __future__ import unicode_literals


class ExportAppException(Exception):
    pass


class BadExportConfiguration(ExportAppException):
    pass


class ExportFormValidationException(Exception):
    pass


class ExportAsyncException(Exception):
    pass
