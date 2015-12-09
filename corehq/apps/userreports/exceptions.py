class UserReportsError(Exception):
    pass


class UserReportsWarning(Warning):
    pass


class TableNotFoundWarning(UserReportsWarning):
    pass


class BadBuilderConfigError(UserReportsError):
    pass


class ColumnNotFoundError(UserReportsError):
    pass


class BadSpecError(UserReportsError):
    pass


class UserQueryError(UserReportsError):
    pass


class TableRebuildError(UserReportsError):
    pass


class StaleRebuildError(TableRebuildError):
    pass


class UserReportsFilterError(UserReportsError):
    pass


class SortConfigurationError(UserReportsError):
    pass


class DataSourceConfigurationNotFoundError(BadSpecError):
    pass


class ReportConfigurationNotFoundError(UserReportsError):
    pass
