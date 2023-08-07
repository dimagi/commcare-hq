class NoAccountException(Exception):
    """
    Raised when trying to access the account of someone without one
    """
    pass


class InvalidRequestException(Exception):
    pass


class IllegalAccountConfirmation(Exception):
    pass


class MissingRoleException(Exception):
    """
    Raised when encountering a WebUser without a role
    """
    pass
