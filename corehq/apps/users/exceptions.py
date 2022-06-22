class NoAccountException(Exception):
    """
    Raised when trying to access the account of someone without one
    """
    pass


class InvalidMobileWorkerRequest(Exception):
    pass


class IllegalAccountConfirmation(Exception):
    pass


class MissingRoleException(Exception):
    """
    Raised when encountering a WebUser without a role
    """
    pass


class ReservedUsernameException(Exception):
    """Raised if username is a reserved name (e.g., admin)"""
    def __init__(self, username):
        self.username = username
