

class NoAccountException(Exception):
    """
    Raised when trying to access the account of someone without one
    """
    pass


class InvalidMobileWorkerRequest(Exception):
    pass
