from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.utils.couch.cache.cache_core import get_redis_client

EXPONENTIAL_RATE = 2
BASE_TIME = 5
MAX_TIME = 60


class RedisExponentialBackoff(object):
    @classmethod
    def get_next_time(cls, event_key, base_time=BASE_TIME, max_time=MAX_TIME):
        if not event_key:
            return base_time
        repeat_number = cls.redis_client().incr(cls.format_key(event_key)) - 1
        exponential = cls.exponential(base_time, EXPONENTIAL_RATE, repeat_number)
        return exponential if exponential < MAX_TIME else max_time

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
