

class CouchExportException(Exception):
    pass


class CustomExportValidationError(CouchExportException):
    pass


class SchemaInferenceError(CouchExportException):
    pass


class SchemaMismatchException(CouchExportException):
    pass


class UnsupportedExportFormat(CouchExportException):
    pass


class ExportRebuildError(CouchExportException):
    pass