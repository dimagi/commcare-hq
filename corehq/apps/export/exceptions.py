



class ExportAppException(Exception):
    pass


class BadExportConfiguration(ExportAppException):
    pass


class ExportFormValidationException(Exception):
    pass


class ExportAsyncException(Exception):
    pass


class ExportODataDuplicateLabelException(Exception):
    pass


class RejectedStaleExport(Exception):
    pass


class InvalidLoginException(Exception):
    pass
