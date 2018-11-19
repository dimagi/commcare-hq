from sqlalchemy.exc import ProgrammingError


class UserReportsError(Exception):
    pass


class UserReportsWarning(Warning):
    pass


class TableNotFoundWarning(UserReportsWarning):
    pass


class MissingColumnWarning(UserReportsWarning):
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


class StaticDataSourceConfigurationNotFoundError(DataSourceConfigurationNotFoundError):
    pass


class ReportConfigurationNotFoundError(UserReportsError):
    pass


class InvalidQueryColumn(UserReportsError):
    pass


class InvalidDataSourceType(UserQueryError):
    pass


def translate_programming_error(exception):
    if isinstance(exception, ProgrammingError):
        orig = getattr(exception, 'orig')
        if orig:
            error_code = getattr(orig, 'pgcode')
            # http://www.postgresql.org/docs/9.4/static/errcodes-appendix.html
            if error_code == '42P01':
                return TableNotFoundWarning
            elif error_code == '42703':
                return MissingColumnWarning
