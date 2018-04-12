from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib
from django.core.cache import cache


class CacheExponential(object):
    klass_key = "django-exp"

    @classmethod
    def _get_cache_key(cls, key):
        key_hash = hashlib.md5(key).hexdigest() if key else ''
        return '{}.{}'.format(cls.klass_key, key_hash)

    @classmethod
    def increment(cls, key):
        cache_key = cls._get_cache_key(key)
        try:
            return cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1)
            return 1

    @classmethod
    def invalidate(cls, event_key):
        cache.delete(cls._get_cache_key(event_key))


class ExponentialBackoff(CacheExponential):
    """
    Exponential backoff contains two external facing methods for handling
    backoff. The `increment` method updates the key's hit count and the
    `should_backoff` method checks if you should backoff based on whether
    the number of hits is a power of 2
    """

    klass_key = "django-exp-backoff"

    @classmethod
    def _number_is_power_of_two(cls, x):
        # it turns out that x & (x - 1) == 0 if and only if x is a power of two
        # http://stackoverflow.com/a/600306/240553
        return x > 0 and (x & (x - 1) == 0)

    @classmethod
    def should_backoff(cls, key):
        cache_key = cls._get_cache_key(key)
        return not cls._number_is_power_of_two(cache.get(cache_key) or 1)


def is_rate_limited(rate_limit_key):
    ExponentialBackoff.increment(rate_limit_key)
    return ExponentialBackoff.should_backoff(rate_limit_key)


class ExponentialGrowth(CacheExponential):
    klass_key = "django-exp-growth"

    EXPONENTIAL_RATE = 2
    BASE_TIME = 5
    MAX_TIME = 60

    @classmethod
    def get_next_time(cls, event_key, base_time=BASE_TIME, max_time=MAX_TIME):
        if not event_key:
            return base_time
        repeat_number = cls.increment(event_key) - 1
        exponential = cls._exponential(
            base_time, cls.EXPONENTIAL_RATE, repeat_number)
        return exponential if exponential < max_time else max_time

    @staticmethod
    def _exponential(base_time, exponential_rate, repeat_number):
        return base_time * exponential_rate ** repeat_number
