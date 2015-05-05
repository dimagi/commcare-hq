import hashlib
from django.core.cache import cache


class ExponentialBackoff(object):
    """
    Exponential backoff contains two external facing methods for handling
    backoff. The `increment` method updates the key's hit count and the
    `should_backoff` method checks if you should backoff based on whether
    the number of hits is a power of 2
    """

    @classmethod
    def _get_cache_key(cls, key):
        key_hash = hashlib.md5(key).hexdigest() if key else ''
        return u'django-exp-backoff.{}'.format(key_hash)

    @classmethod
    def _number_is_power_of_two(cls, x):
        # it turns out that x & (x - 1) == 0 if and only if x is a power of two
        # http://stackoverflow.com/a/600306/240553
        return x > 0 and (x & (x - 1) == 0)

    @classmethod
    def increment(cls, key):
        cache_key = cls._get_cache_key(key)
        try:
            return cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1)
            return 1

    @classmethod
    def should_backoff(cls, key):
        cache_key = cls._get_cache_key(key)
        return not cls._number_is_power_of_two(cache.get(cache_key) or 1)
