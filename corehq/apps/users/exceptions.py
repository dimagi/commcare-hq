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


class InvalidUsernameException(Exception):
    """Raised if username contains invalid characters"""
    def __init__(self, username):
        self.username = username


class UsernameAlreadyExists(Exception):
    """Raised if username is associated with a current or deleted user"""
    def __init__(self, username, is_deleted):
        self.username = username
        self.is_deleted = is_deleted
