from __future__ import absolute_import
from collections import namedtuple

from django.core.cache import caches
from .quickcache import ConfigMixin, get_quickcache, assert_function
from .cache_helpers import CacheWithTimeout, TieredCache
from .quickcache_helper import QuickCacheHelper


class DjangoQuickCache(namedtuple('DjangoQuickCache', [
    'vary_on',
    'skip_arg',
    'timeout',
    'memoize_timeout',
    'helper_class',
    'assert_function',
]), ConfigMixin):

    def call(self):
        cache = tiered_django_cache([('locmem', self.memoize_timeout), ('default', self.timeout)])
        return get_quickcache(
            cache=cache,
            vary_on=self.vary_on,
            skip_arg=self.skip_arg,
            helper_class=self.helper_class,
            assert_function=self.assert_function,
        ).call()


def tiered_django_cache(cache_name_timeout_pairs):
    return TieredCache([
        CacheWithTimeout(caches[cache_name], timeout)
        for cache_name, timeout in cache_name_timeout_pairs
        if timeout
    ])

get_django_quickcache = DjangoQuickCache(
    vary_on=Ellipsis,
    skip_arg=None,
    timeout=Ellipsis,
    memoize_timeout=Ellipsis,
    helper_class=QuickCacheHelper,
    assert_function=assert_function,
).but_with
