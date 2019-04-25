from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext as _

from psycopg2 import errorcodes
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


class DuplicateColumnIdError(BadSpecError):
    def __init__(self, columns, *args, **kwargs):
        self.columns = columns
        super(DuplicateColumnIdError, self).__init__(*args, **kwargs)

    def __str__(self):
        return _('Report contains duplicate column ids: {}').format(', '.join(set(self.columns)))


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


class ValidationError(UserReportsError):
    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        return '\n'.join("{}: {}".format(e[0], e[1]) for e in self.errors)


def translate_programming_error(exception):
    if isinstance(exception, ProgrammingError):
        orig = getattr(exception, 'orig')
        if orig:
            if orig.pgcode == errorcodes.UNDEFINED_TABLE:
                return TableNotFoundWarning(str(exception))
            elif orig.pgcode == errorcodes.UNDEFINED_COLUMN:
                return MissingColumnWarning(str(exception))
