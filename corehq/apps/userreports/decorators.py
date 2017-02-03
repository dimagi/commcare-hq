from functools import wraps

from django.conf import settings

from sqlagg import (
    ColumnNotFoundException,
    TableNotFoundException,
)
from sqlalchemy.exc import ProgrammingError

from corehq.apps.userreports.exceptions import (
    InvalidQueryColumn,
    TableNotFoundWarning,
    UserReportsError,
)
from corehq.util.soft_assert import soft_assert
import six

_soft_assert = soft_assert(
    to='{}@{}'.format('npellegrino+ucr-get-data', 'dimagi.com'),
    exponential_backoff=False,
)


def catch_and_raise_exceptions(func):
    @wraps(func)
    def _inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (
            ColumnNotFoundException,
            ProgrammingError,
            InvalidQueryColumn,
        ) as e:
            if not settings.UNIT_TESTING:
                _soft_assert(False, six.text_type(e))
            raise UserReportsError(six.text_type(e))
        except TableNotFoundException:
            raise TableNotFoundWarning
    return _inner
