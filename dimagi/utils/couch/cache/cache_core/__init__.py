from django.conf import settings
from django.core import cache

COUCH_CACHE_TIMEOUT = 43200
MOCK_REDIS_CACHE = None

DEBUG_TRACE = False

CACHE_DOCS = getattr(settings, 'COUCH_CACHE_DOCS', False)
CACHE_VIEWS = getattr(settings, 'COUCH_CACHE_VIEWS', False)


CACHED_VIEW_PREFIX = '#cached_view_'

#the actual payload of the cached_doc
CACHED_DOC_PREFIX = '#cached_doc_'
CACHED_DOC_PROP_PREFIX = '#cached_doc_helper_'

def rcache():
    return MOCK_REDIS_CACHE or cache.get_cache('redis')

def key_doc_prop(doc_id, prop_name):
    return ':'.join([CACHED_DOC_PROP_PREFIX, doc_id, prop_name])

def key_doc_id(doc_id):
    """
    Redis cache key for a full couch document by doc_id
    """
    ret = ":".join([CACHED_DOC_PREFIX, doc_id])
    return ret



from .api import *
from .gen import *