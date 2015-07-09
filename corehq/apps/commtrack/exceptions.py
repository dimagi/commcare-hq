class LinkedSupplyPointNotFoundError(Exception):
    pass


class NotAUserClassError(Exception):
    pass


class InvalidProductException(Exception):
    pass


class DuplicateProductCodeException(InvalidProductException):
    pass


class NoDefaultLocationException(Exception):
    pass


class MultipleSupplyPointException(Exception):
    pass


class MissingProductId(Exception):
    pass


class InvalidSMSAction(Exception):
    """
    For SMS things that have been deprecated/removed
    """
    pass
