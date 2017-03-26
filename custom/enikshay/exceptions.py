class ENikshayException(Exception):
    pass


class ENikshayCaseNotFound(ENikshayException):
    pass


class NikshayLocationNotFound(ENikshayException):
    pass


class NikshayCodeNotFound(ENikshayException):
    pass


class RequiredValueMissing(ENikshayException):
    pass
