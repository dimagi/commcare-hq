import hashlib
from django.core.cache import cache


class ExponentialCache(object):
    """ ExponentialCache interfaces with the cache for the growth and backoff classes

    The `increment` function updates the key's hit count and the `delete_key` function clears it
    """

    @classmethod
    def _get_cache_key(cls, key):
        if isinstance(key, str):
            key = key.encode('utf-8')
        key_hash = hashlib.md5(key).hexdigest() if key else ''
        return 'django-exp-backoff.{}'.format(key_hash)

    @classmethod
    def increment(cls, key):
        cache_key = cls._get_cache_key(key)
        try:
            return cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1)
            return 1

    @classmethod
    def delete_key(cls, key):
        try:
            cache.delete(cls._get_cache_key(key))
        except ValueError:
            pass


class ExponentialBackoff(ExponentialCache):
    """ ExponentialBackoff provides functions for slowly backing off

    The `should_backoff` method checks if you should backoff based on whether
    the number of hits is a power of 2
    """
    @classmethod
    def should_backoff(cls, key):
        cache_key = cls._get_cache_key(key)
        return not cls._number_is_power_of_two(cache.get(cache_key) or 1)

    @classmethod
    def _number_is_power_of_two(cls, x):
        # it turns out that x & (x - 1) == 0 if and only if x is a power of two
        # http://stackoverflow.com/a/600306/240553
        return x > 0 and (x & (x - 1) == 0)


class ExponentialGrowth(ExponentialCache):
    @classmethod
    def exponential(cls, key, base):
        cache_key = cls._get_cache_key(key)
        return base ** (cache.get(cache_key) or 0)


def is_rate_limited(rate_limit_key):
    ExponentialBackoff.increment(rate_limit_key)
    return ExponentialBackoff.should_backoff(rate_limit_key)


def get_exponential(rate_limit_key, exponential_base=2):
    ExponentialGrowth.increment(rate_limit_key)
    return ExponentialGrowth.exponential(rate_limit_key, exponential_base)


def clear_limit(rate_limit_key):
    ExponentialCache.delete_key(rate_limit_key)
