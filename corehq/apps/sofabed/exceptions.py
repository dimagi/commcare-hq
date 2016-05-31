
class InvalidDataException(Exception):
    pass


class InvalidDomainException(InvalidDataException):
    pass


class InvalidMetaBlockException(InvalidDataException):
    pass


class InvalidFormUpdateException(InvalidDataException):
    pass


class InvalidCaseUpdateException(InvalidDataException):
    pass
