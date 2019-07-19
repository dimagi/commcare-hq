from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib
import inspect
from functools import wraps

from django.conf import settings

from sqlagg import (
    ColumnNotFoundException,
)
from sqlalchemy.exc import ProgrammingError

from corehq.apps.userreports.exceptions import (
    InvalidQueryColumn,
    UserReportsError,
    translate_programming_error, TableNotFoundWarning)
from corehq.util.soft_assert import soft_assert
import six

_soft_assert = soft_assert(
    exponential_backoff=True,
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
            error = translate_programming_error(e)
            if isinstance(error, TableNotFoundWarning):
                raise error
            if not settings.UNIT_TESTING:
                _soft_assert(False, six.text_type(e))
            raise UserReportsError(six.text_type(e))
    return _inner


def ucr_context_cache(vary_on=()):
    """
    Decorator which caches calculations performed during a UCR EvaluationContext
    The decorated function or method must have a parameter called 'context'
    which will be used by this decorator to store the cache.
    """
    def decorator(fn):
        assert 'context' in fn.__code__.co_varnames
        assert isinstance(vary_on, tuple)

        @wraps(fn)
        def _inner(*args, **kwargs):
            # shamelessly stolen from quickcache
            callargs = inspect.getcallargs(fn, *args, **kwargs)
            context = callargs['context']
            prefix = '{}.{}'.format(
                fn.__name__[:40] + (fn.__name__[40:] and '..'),
                hashlib.md5(inspect.getsource(fn).encode('utf-8')).hexdigest()[-8:]
            )
            cache_key = (prefix,) + tuple(callargs[arg_name] for arg_name in vary_on)
            if context.exists_in_cache(cache_key):
                return context.get_cache_value(cache_key)
            res = fn(*args, **kwargs)
            context.set_cache_value(cache_key, res)
            return res
        return _inner
    return decorator
