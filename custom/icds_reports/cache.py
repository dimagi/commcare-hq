from __future__ import absolute_import
from __future__ import unicode_literals

from quickcache import get_quickcache
from quickcache.django_quickcache import tiered_django_cache

from corehq.sql_db.routers import forced_citus
from corehq.util.quickcache import quickcache_soft_assert, get_session_key


def get_default_prefix():
    return 'c' if forced_citus() else ''


def get_locmem_prefix():
    return get_session_key() + get_default_prefix()


cache = tiered_django_cache([
    ('locmem', 10, get_locmem_prefix),
    ('default', 5 * 60, get_default_prefix)
])


# Custom cache that varies the key depending on if request is sent to CitusDB or not
icds_quickcache = get_quickcache(
    cache=cache,
    assert_function=quickcache_soft_assert,
)
