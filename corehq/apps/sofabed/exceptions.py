
class InvalidDataException(Exception):
    pass


class InvalidMetaBlockException(InvalidDataException):
    pass


class InvalidFormUpdateException(InvalidDataException):
    pass


class InvalidCaseUpdateException(InvalidDataException):
    pass
