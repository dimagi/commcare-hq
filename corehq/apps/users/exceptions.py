class NoAccountException(Exception):
    """
    Raised when trying to access the account of someone without one
    """
    pass

class InvalidLocationConfig(Exception):
    pass


class UserUploadError(Exception):
    pass
