

class FilterException(Exception):
    """
    Exceptions involving report filters.
    """
    pass


class MissingParamException(FilterException):
    pass


class FilterValueException(FilterException):
    pass
