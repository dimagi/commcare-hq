class ApplicationNotFoundError(Exception):
    pass


class UserReportsError(Exception):
    pass


class UserReportsWarning(Warning):
    pass


class TableNotFoundWarning(UserReportsWarning):
    pass


class BadSpecError(UserReportsError):
    pass


class UserQueryError(UserReportsError):
    pass


class TableRebuildError(UserReportsError):
    pass


class UserReportsFilterError(UserReportsError):
    pass


class SortConfigurationError(UserReportsError):
    pass
