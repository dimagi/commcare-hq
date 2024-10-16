from abc import ABC, abstractmethod
import copy

from django.core.cache import cache


class CacheStore(ABC):
    """
    Use this to store and retrieve data in memory for prototyped features,
    especially for prototypes using HTMX.

    DO NOT USE with released features! Prototypes only.
    """
    timeout = 2 * 60 * 60

    def __init__(self, request):
        self.username = request.user.username

    @property
    @abstractmethod
    def slug(self):
        raise NotImplementedError("please specify a 'slug'")

    @property
    @abstractmethod
    def default_value(self):
        """
        Please make sure the default value can be properly pickled and stored
        in cached memory. Safe options are strings, dicts, and lists of strings.
        If you want to store more complicated objects, perhaps it's time to start
        using a database. Please remember this is only for prototyping and examples!
        """
        raise NotImplementedError("please specify a 'default_value'")

    @property
    def cache_key(self):
        return f"{self.username}:prototype:{self.slug}"

    def set(self, data):
        cache.set(self.cache_key, data, self.timeout)

    def get(self):
        return cache.get(self.cache_key, copy.deepcopy(self.default_value))

    def delete(self):
        cache.delete(self.cache_key)
