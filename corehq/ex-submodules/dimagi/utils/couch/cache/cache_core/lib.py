from __future__ import absolute_import
from __future__ import unicode_literals
import simplejson
from . import CACHE_DOCS, key_doc_id, rcache


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
