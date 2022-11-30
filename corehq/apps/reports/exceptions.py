

class BadRequestError(Exception):
    """
    For catching client-side errors.
    Views should catch and return HTTP400 or similar
    """
    pass


class InvalidDaterangeException(Exception):
    pass


class TooMuchDataError(Exception):
    pass


class TableauAPIError(Exception):
    def __init__(self, message, code=None):
        if code:
            self.code = int(code)
        super().__init__(message)
