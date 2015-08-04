class BadRequestError(Exception):
    """
    For catching client-side errors.
    Views should catch and return HTTP400 or similar
    """
    pass


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


class InvalidDaterangeException(Exception):
    pass
