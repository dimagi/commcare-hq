from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple

from quickcache import get_quickcache
from quickcache.django_quickcache import tiered_django_cache
from quickcache.quickcache import ConfigMixin

from corehq.sql_db.routers import forced_citus
from corehq.util.quickcache import quickcache_soft_assert, get_session_key


def get_default_prefix():
    return 'c' if forced_citus() else ''


def get_locmem_prefix():
    return get_session_key() + get_default_prefix()


# Custom cache that varies the key depending on if request is sent to CitusDB or not
class ICDSQuickCache(namedtuple('ICDSQuickCache', [
    'vary_on',
    'skip_arg',
    'timeout',
    'memoize_timeout',
]), ConfigMixin):

    def call(self):
        cache = tiered_django_cache([
            ('locmem', self.memoize_timeout, get_locmem_prefix),
            ('default', self.timeout, get_default_prefix)
        ])

        return get_quickcache(
            cache=cache,
            vary_on=self.vary_on,
            skip_arg=self.skip_arg,
            assert_function=quickcache_soft_assert,
        ).call()


icds_quickcache = ICDSQuickCache(
    vary_on=Ellipsis,
    skip_arg=None,
    timeout=5 * 60,
    memoize_timeout=10,
)
