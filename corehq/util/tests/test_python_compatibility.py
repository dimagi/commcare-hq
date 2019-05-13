from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime

from django.core.cache import caches

from testil import eq

from corehq.util.quickcache import quickcache


def test_py2to3_caching():
    @quickcache([])
    def get_value():
        raise Exception("should not get here")

    # decoded_value pickled by Python 2
    value = b'\x80\x02]q\x01cdatetime\ndatetime\nq\x02U\n\x07\xe3\x05\r\x15\x181\x07\xe15\x85Rq\x03a.'
    decoded_value = [datetime(2019, 5, 13, 21, 24, 49, 516405)]

    cache = caches['redis'].client
    quickcache_key = get_value.get_cache_key()
    redis_key = cache.make_key(quickcache_key)
    redis = cache.get_client()
    redis.set(redis_key, value, px=3000)
    eq(redis.get(redis_key), value)

    eq(get_value(), decoded_value)
