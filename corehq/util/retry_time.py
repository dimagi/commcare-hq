from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.utils.couch.cache.cache_core import get_redis_client
from casexml.apps.phone.const import ASYNC_RETRY_AFTER

EXPONENTIAL_RATE = 2


class RedisExponentialBackoff(object):
    @classmethod
    def get_next_time(cls, event_key, base_time=ASYNC_RETRY_AFTER):
        if not event_key:
            return base_time
        repeat_number = cls.redis_client().incr(cls.format_key(event_key)) - 1
        return cls.exponential(base_time, EXPONENTIAL_RATE, repeat_number)

    @classmethod
    def invalidate(cls, event_key):
        cls.redis_client().delete(cls.format_key(event_key))

    @staticmethod
    def format_key(event_key):
        return "%s.%s" % ("exponential", event_key)

    @staticmethod
    def exponential(base_time, exponential_rate, repeat_number):
        return base_time * exponential_rate ** repeat_number

    @staticmethod
    def redis_client():
        return get_redis_client().client.get_client()
