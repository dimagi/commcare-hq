

class ExportAppException(Exception):
    pass


class BadExportConfiguration(ExportAppException):
    pass


class ExportNotFound(ExportAppException):
    pass
