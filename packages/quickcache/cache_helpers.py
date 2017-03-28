from collections import namedtuple
from .logger import logger


class CacheWithTimeout(namedtuple('CacheWithTimeout', ['cache', 'timeout'])):

    def get(self, key, default=None):
        return self.cache.get(key, default=default)

    def set(self, key, value):
        return self.cache.set(key, value, timeout=self.timeout)

    def delete(self, key):
        return self.cache.delete(key)


class TieredCache(object):
    """
    Tries a number of caches in increasing order.
    Caches should be ordered with faster, more local caches at the beginning
    and slower, more shared caches towards the end

    Relies on each of the caches' default timeout;
    TieredCache.set doesn't accept a timeout parameter

    """

    def __init__(self, caches):
        self.caches = caches

    def get(self, key, default=None):
        missed = []
        for cache in self.caches:
            content = cache.get(key, default=Ellipsis)
            if content is not Ellipsis:
                for missed_cache in missed:
                    missed_cache.set(key, content)
                logger.debug('missed caches: {}'.format([c.__class__.__name__
                                                         for c in missed]))
                logger.debug('hit cache: {}'.format(cache.__class__.__name__))
                return content
            else:
                missed.append(cache)
        return default

    def set(self, key, value):
        for cache in self.caches:
            cache.set(key, value)

    def delete(self, key):
        for cache in self.caches:
            cache.delete(key)
