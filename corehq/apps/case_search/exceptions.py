class CaseSearchException(Exception):
    pass


class CaseSearchNotEnabledException(CaseSearchException):
    pass


class CaseSearchUserError(CaseSearchException):
    pass
