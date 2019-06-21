from __future__ import unicode_literals


class UnsupportedSavedReportError(Exception):
    """
    For unknown (discontinued/legacy) saved-reports
    """
    pass


class UnsupportedScheduledReportError(Exception):
    """
    For unknown (discontinued/legacy) scheduled-reports
    """
    pass
