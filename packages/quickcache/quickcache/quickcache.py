# coding=utf-8
from collections import namedtuple
import functools

from .quickcache_helper import QuickCacheHelper


class ConfigMixin(object):
    def but_with(self, **defaults):
        return self._replace(**defaults)

    def __call__(self, vary_on=Ellipsis, skip_arg=Ellipsis, **new_values):
        if vary_on is not Ellipsis:
            new_values['vary_on'] = vary_on
        if skip_arg is not Ellipsis:
            new_values['skip_arg'] = skip_arg

        if new_values:
            return self.but_with(**new_values).__call__()

        missing_values = [key for key, value in self._asdict().items()
                          if value is Ellipsis]
        if missing_values:
            raise ValueError(
                'the quickcache decorator still needs values '
                'for the following parameters: {}'.format(missing_values))

        return self.call()

    def call(self):
        helper_class_kwargs = self._asdict()
        helper_class = helper_class_kwargs.pop('helper_class')

        def decorator(fn):
            helper = helper_class(fn, **helper_class_kwargs)

            @functools.wraps(fn)
            def inner(*args, **kwargs):
                return helper(*args, **kwargs)

            inner.clear = helper.clear
            inner.get_cache_key = helper.get_cache_key
            inner.prefix = helper.prefix
            inner.get_cached_value = helper.get_cached_value

            return inner

        return decorator


class QuickCache(namedtuple('QuickCache', [
    'vary_on',
    'cache',
    'skip_arg',
    'helper_class',
]), ConfigMixin):
    pass

get_quickcache = QuickCache(
    vary_on=Ellipsis,
    cache=Ellipsis,
    skip_arg=None,
    helper_class=QuickCacheHelper,
).but_with
