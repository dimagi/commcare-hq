# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.core.cache import caches
from .quickcache import generic_quickcache
from .cache_helpers import CacheWithTimeout, TieredCache


def tiered_django_cache(cache_name_timeout_pairs):
    return TieredCache([
        CacheWithTimeout(caches[cache_name], timeout)
        for cache_name, timeout in cache_name_timeout_pairs
        if timeout
    ])


def quickcache(vary_on, skip_arg=None, timeout=None, memoize_timeout=None):
    """
    An easy "all-purpose" cache decorator

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
    timeout = timeout if timeout is not None else 5 * 60
    memoize_timeout = memoize_timeout if memoize_timeout else 10
    cache = tiered_django_cache([('locmem', memoize_timeout), ('default', timeout)])
    return generic_quickcache(vary_on, cache=cache, skip_arg=skip_arg)
