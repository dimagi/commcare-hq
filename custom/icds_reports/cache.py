from __future__ import absolute_import
from __future__ import unicode_literals

from quickcache import get_quickcache, ForceSkipCache
from quickcache.django_quickcache import tiered_django_cache

from corehq.sql_db.routers import forced_citus
from corehq.util.quickcache import quickcache_soft_assert, get_session_key


def get_cache_prefix_func(catch_force_skip=False):
    def prefix_func():
        try:
            prefix = get_session_key()
        except ForceSkipCache:
            if not catch_force_skip:
                raise
            else:
                prefix = ''

        if forced_citus():
            prefix += 'c'
        return prefix

    return prefix_func


cache = tiered_django_cache([
    ('locmem', 10, get_cache_prefix_func()),
    ('default', 5 * 60, get_cache_prefix_func(catch_force_skip=True))
])


# Custom cache that varies the key depending on if request is sent to CitusDB or not
icds_quickcache = get_quickcache(
    cache=cache,
    assert_function=quickcache_soft_assert,
)
