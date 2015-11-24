

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
