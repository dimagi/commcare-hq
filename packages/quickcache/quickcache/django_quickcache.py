# -*- coding: utf-8 -*-
"""
An easy "all-purpose" cache decorator with support for django caches

Examples:
    - caching a singleton function, refresh every 5 minutes

        @quickcache([], timeout=5 * 60)
        def get_config_from_db():
            # ...

    - vary on the arguments of a function

        @quickcache(['request.couch_user._rev'], timeout=24 * 60 * 60)
        def domains_for_user(request):
            return [Domain.get_by_name(domain)
                    for domain in request.couch_user.domains]

      now as soon as request.couch_user._rev has changed,
      the function will be recomputed

    - skip the cache based on the value of a particular arg

        @quickcache(['name'], skip_arg='force')
        def get_by_name(name, force=False):
            # ...

    - skip_arg can also be a function and will receive the save arguments as the function:

        def skip_fn(name, address):
            return name == 'Ben' and 'Chicago' not in address

        @quickcache(['name'], skip_arg=skip_fn)
        def get_by_name_and_address(name, address):
            # ...

Features:
    - In addition to caching in the default shared cache,
      quickcache caches in memory for 10 seconds
      (conceptually the length of a single request).
      This can be overridden to a different number with memoize_timeout.

    - In addition to varying on the arguments and the name of the function,
      quickcache will also make sure to vary
      on the _source code_ of your function.
      That way if you change the behavior of the function, there won't be
      any stale cache when you deploy.

    - Can vary on any number of the function's parameters

    - Does not by default vary on all function parameters.
      This is because it is not in general obvious what it means
      to vary on an object, for example.

    - Allows you to vary on an attribute of an object,
      multiple attrs of the same object, attrs of attrs of an object, etc

    - Allows you to pass in a function as the vary_on arg which will get called
      with the same args and kwargs as the function. It should return a list of simple
      values to be used for generating the cache key.

    Note on unicode and strings in vary_on:
      When strings and unicode values are used as vary on parameters they will result in the
      same cache key if and only if the string values are UTF-8 or ascii encoded.
      e.g.
      u'namé' and 'nam\xc3\xa9' (UTF-8 encoding) will result in the same cache key
      BUT
      u'namé' and 'nam\xe9' (latin-1 encoding) will NOT result in the same cache key


"""
from __future__ import absolute_import
from collections import namedtuple

from django.core.cache import caches
from .quickcache import ConfigMixin, get_quickcache
from .cache_helpers import CacheWithTimeout, TieredCache
from .quickcache_helper import QuickCacheHelper


class DjangoQuickCache(namedtuple('DjangoQuickCache', [
    'vary_on',
    'skip_arg',
    'timeout',
    'memoize_timeout',
    'helper_class',
]), ConfigMixin):

    def call(self):
        cache = tiered_django_cache([('locmem', self.memoize_timeout), ('default', self.timeout)])
        return get_quickcache(
            cache=cache,
            vary_on=self.vary_on,
            skip_arg=self.skip_arg,
            helper_class=self.helper_class,
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
).but_with
