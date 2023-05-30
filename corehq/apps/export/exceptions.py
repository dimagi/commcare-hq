from django.utils.translation import gettext_lazy
from corehq.apps.export.const import MAX_CASE_TYPE_COUNT, MAX_APP_COUNT

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


class ExportTooLargeException(Exception):
    """Export exceeds size limit"""


class CaseTypeOrAppLimitExceeded(Exception):
    """Project exceeds max allowed case types or applications for a bulk export"""
    message = gettext_lazy(
        "Cannot do a bulk case export as the project has more than %(max_case_types)s "
        "case types or %(max_apps)s applications."
    ) % {
        'max_case_types': MAX_CASE_TYPE_COUNT,
        'max_apps': MAX_APP_COUNT
    }

    def __init__(self, msg=None, *args, **kwargs):
        if msg:
            self.message = msg
        super().__init__(self.message, *args, **kwargs)


class NoTablesException(Exception):
    """ExportInstance does not have any tables to export"""
