from __future__ import absolute_import
from __future__ import unicode_literals
import simplejson
from django_redis.cache import RedisCache
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
