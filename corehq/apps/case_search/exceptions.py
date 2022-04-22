class CaseSearchException(Exception):
    pass


class CaseSearchNotEnabledException(CaseSearchException):
    pass


class CaseSearchUserError(CaseSearchException):
    pass


class CaseFilterError(Exception):

    def __init__(self, message, filter_part):
        self.filter_part = filter_part
        super(CaseFilterError, self).__init__(message)


class TooManyRelatedCasesError(CaseFilterError):
    pass


class XPathFunctionException(CaseFilterError):
    pass
