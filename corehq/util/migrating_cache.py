from django.core.cache.backends.base import BaseCache
from django.core import cache


class MigratingCache(BaseCache):

    def __init__(self, params):
        self.old_cache = cache.caches[params['OPTIONS']['old_cache']]
        self.new_cache = cache.caches[params['OPTIONS']['new_cache']]

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """
        Set a value in the cache if the key does not already exist. If
        timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.

        Returns True if the value was stored, False otherwise.
        """
        if not self.new_cache.add(key, value, timeout=timeout, version=version):
            return self.old_cache.add(key, value, timeout=timeout, version=version)

    def get(self, key, default=None, version=None):
        """
        Fetch a given key from the cache. If the key does not exist, return
        default, which itself defaults to None.
        """
        new_value = self.new_cache.get(key, default=default, version=version)
        if new_value is None:
            return self.old_cache.get(key, default=default, version=version)
        else:
            return new_value

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        self.new_cache.set(self, key, value, timeout=timeout, version=version)

    def delete(self, key, version=None):
        self.old_cache.delete(key, version=version)
        self.new_cache.delete(key, version=version)

    def clear(self):
        self.old_cache.clear()
        self.new_cache.clear()

    def close(self, **kwargs):
        self.old_cache.close(**kwargs)
        self.new_cache.close(**kwargs)
