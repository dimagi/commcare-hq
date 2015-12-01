from inspect import getargspec

import functools
from django.conf import settings


def should_use_sql_backend(domain):
    if settings.UNIT_TESTING:
        override = getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', None)
        if override is not None:
            return override
    # uncomment when ready for production
    # return USE_SQL_BACKEND.enabled(domain)
    return False


def cache_return_value(fn):
    """
    Docorator to save the return value of a method or property.
    Use this where you can't use quickcache or memoize because you can't
    guarantee a consistent or unique lookup key e.g. forms that get deprecated

    Requires that the first arg is 'self' and that no other args or kwargs are being
    passed in.

    Note that there is no provision for caching different return values. Once a value
    is cached it will always return the same value regardless of any changes to internal
    state of the object.

    :param fn: a function or property with no args (other than 'self')
    """
    cached_property_name = '{}__cached_value'.format(fn.__name__)

    argspec = getargspec(fn)
    assert argspec.args and argspec.args[0] == 'self'

    @functools.wraps(fn)
    def _inner(*args, **kwargs):
        assert len(args) == 1 and not kwargs, 'no args or kwargs allowed on cached methods'
        obj = args[0]

        cached_value = getattr(obj, cached_property_name, Ellipsis)
        if cached_value is not Ellipsis:
            return cached_value

        value = fn(*args, **kwargs)
        setattr(obj, cached_property_name, value)
        return value

    return _inner
