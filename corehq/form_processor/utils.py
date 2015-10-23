from django.conf import settings
import functools
import types
import collections
from corehq.toggles import USE_SQL_BACKEND


class ToFromGeneric(object):
    def to_generic(self):
        raise NotImplementedError()

    @classmethod
    def from_generic(cls, obj_dict):
        raise NotImplementedError()


def to_generic(fn):
    """
    Helper decorator to convert from a DB type to a generic type by calling 'to_generic'
    on the db type. e.g. FormData to XFormInstance
    """
    def _wrap(obj):
        if hasattr(obj, 'to_generic'):
            return obj.to_generic()
        elif isinstance(obj, (list, tuple)):
            return [_wrap(ob) for ob in obj]
        elif isinstance(obj, (types.GeneratorType, collections.Iterable)):
            return (_wrap(ob) for ob in obj)
        else:
            return obj

    @functools.wraps(fn)
    def _inner(*args, **kwargs):
        obj = fn(*args, **kwargs)
        return _wrap(obj)

    return _inner


def should_use_sql_backend(domain):
    toggle_to_check = USE_SQL_BACKEND
    if settings.UNIT_TESTING:
        override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
        if override is not None:
            return override
    return toggle_to_check.enabled(domain)
