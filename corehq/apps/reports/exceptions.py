class BadRequestError(Exception):
    """
    For catching client-side errors.
    Views should catch and return HTTP400 or similar
    """
    pass


class UnsupportedSavedReportError(Exception):
    """
    For unknown saved-reports (discontinued/legacy)
    """
    pass
