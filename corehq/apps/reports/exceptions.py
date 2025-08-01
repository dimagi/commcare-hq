class BadRequestError(Exception):
    """
    For catching client-side errors.
    Views should catch and return HTTP400 or similar
    """
    pass


class TooManyOwnerIDsError(Exception):
    """
    Raised if attempting to render a report that filters using too many owner ids
    """


class InvalidDaterangeException(Exception):
    pass


class TooMuchDataError(Exception):
    pass


class TableauAPIError(Exception):
    def __init__(self, message, code=None):
        self.code = int(code) if code else None
        super().__init__(message)
