

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


class ExportInvalidTransform(Exception):
    '''Thrown when an invalid transform constant gets added to an ExportColumn'''
