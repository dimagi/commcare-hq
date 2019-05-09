from __future__ import absolute_import
from __future__ import unicode_literals
import simplejson
import six
from django_redis.cache import RedisCache
from django_redis.util import load_class

from . import CACHE_DOCS, key_doc_id, rcache
from corehq.util.soft_assert import soft_assert


def invalidate_doc_generation(doc):
    from .gen import GenerationCache
    doc_type = doc.get('doc_type', None)
    generation_mgr = GenerationCache.doc_type_generation_map()
    if doc_type in generation_mgr:
        generation_mgr[doc_type].invalidate_all()


def _get_cached_doc_only(doc_id):
    """
    helper cache retrieval method for open_doc - for use by views in retrieving their docs.
    """
    doc = rcache().get(key_doc_id(doc_id), None)
    if doc and CACHE_DOCS:
        return simplejson.loads(doc)
    else:
        return None


class HQRedisCache(RedisCache):

    def _track_call(self):
        hq_assert = soft_assert(['sreddy+redis' + '@' + 'dimagi.com'])
        hq_assert(False, msg="Detected Redis multikey operation")

    def set_many(self, *args, **kwargs):
        self._track_call()
        super(HQRedisCache, self).set_many(*args, **kwargs)

    def get_many(self, *args, **kwargs):
        self._track_call()
        return super(HQRedisCache, self).get_many(*args, **kwargs)

    def delete_many(self, *args, **kwargs):
        self._track_call()
        return super(HQRedisCache, self).delete_many(*args, **kwargs)


# Separate caches for python versions.  Only permit one key in at most one cache but not both at a time.
# Running different processes on different Python versions will mimic a highly volatile cache. (high eviction rate)
# Warning: if key->values are expected to persist, this will not work well
class RedisCacheByPythonVersion(object):

    def __init__(self, *args, **kwargs):
        # Defined in settings
        cache_class = load_class(args[1]['OPTIONS'].get('BACKEND_BASE', 'django_redis.cache.RedisCache'))

        self._python_2_cache = cache_class(*args, **kwargs)

        args[1]['KEY_PREFIX'] = 'py3:' + (args[1].get('KEY_PREFIX') or '')
        self._python_3_cache = cache_class(*args, **kwargs)

    @property
    def _main_cache(self):
        if six.PY3:
            return self._python_3_cache
        return self._python_2_cache

    @property
    def _other_cache(self):
        if six.PY3:
            return self._python_2_cache
        return self._python_3_cache

    def add(self, *args, **kwargs):
        return_val = self._main_cache.add(*args, **kwargs)
        self._other_cache.delete(args[0])
        return return_val

    def set(self, *args, **kwargs):
        return_val = self._main_cache.set(*args, **kwargs)
        self._other_cache.delete(args[0])
        return return_val

    def set_many(self, *args, **kwargs):  # TODO - verify if used.  Might not need if never used in HQ.
        return_val = self._main_cache.set_many(*args, **kwargs)
        self._other_cache.delete_many(*args, **kwargs)
        return return_val

    def clear(self):
        self._other_cache.clear()
        return self._main_cache.clear()

    def close(self, **kwargs):
        self._other_cache.close(**kwargs)
        return self._main_cache.close(**kwargs)

    def delete(self, *args, **kwargs):
        self._other_cache.delete(*args, **kwargs)
        return self._main_cache.delete(*args, **kwargs)

    def delete_pattern(self, *args, **kwargs):
        self._other_cache.delete_pattern(*args, **kwargs)
        return self._main_cache.delete_pattern(*args, **kwargs)

    def delete_many(self, *args, **kwargs):
        self._other_cache.delete_many(*args, **kwargs)
        return self._main_cache.delete_many(*args, **kwargs)

    def incr(self, *args, **kwargs):
        return_val = self._main_cache.incr(*args, **kwargs)
        self._other_cache.delete(args[0])
        return return_val

    def decr(self, *args, **kwargs):
        return_val = self._main_cache.decr(*args, **kwargs)
        self._other_cache.delete(args[0])
        return return_val

    def expire(self, *args, **kwargs):
        return_val = self._main_cache.expire(*args, **kwargs)
        self._other_cache.delete(args[0])
        return return_val

    # Call on the same cache each time

    def lock(self, *args, **kwargs):
        assert isinstance(args[0], six.text_type)
        return self._python_2_cache.lock(*args, **kwargs)

    # Just call on self._main_cache

    @property
    def client(self):
        return self._main_cache.client

    def has_key(self, *args, **kwargs):
        return self._main_cache.has_key(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self._main_cache.get(*args, **kwargs)

    def get_backend_timeout(self, *args, **kwargs):
        return self._main_cache.get_backend_timeout(*args, **kwargs)

    def get_many(self, *args, **kwargs):
        return self._main_cache.get_many(*args, **kwargs)

    def ttl(self, *args, **kwargs):
        return self._main_cache.ttl(*args, **kwargs)

    def iter_keys(self, *args, **kwargs):
        return self._main_cache.iter_keys(*args, **kwargs)

    def keys(self, *args, **kwargs):
        return self._main_cache.keys(*args, **kwargs)

    def __contains__(self, key):
        return self._main_cache.__contains__(key)

    # Don't implement unused subset of the interface

    def make_key(self, *args, **kwargs):
        raise NotImplementedError

    def get_or_set(self, *args, **kwargs):
        raise NotImplementedError

    def validate_key(self, *args, **kwargs):
        raise NotImplementedError

    def incr_version(self, *args, **kwargs):
        raise NotImplementedError

    def decr_version(self, *args, **kwargs):
        raise NotImplementedError

    def persist(self, *args, **kwargs):
        raise NotImplementedError

    def touch(self, *args, **kwargs):
        raise NotImplementedError
