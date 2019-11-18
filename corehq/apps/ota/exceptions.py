

class PrimeRestoreException(Exception):
    pass


class PrimeRestoreUserException(PrimeRestoreException):
    pass


class RestorePermissionDenied(Exception):
    """ Raised when the user is not permitted to restore """
