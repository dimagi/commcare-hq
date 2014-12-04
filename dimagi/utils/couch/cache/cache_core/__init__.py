import logging
from django.conf import settings
from django.core import cache
from django.core.cache import InvalidCacheBackendError

log = logging.getLogger(__name__)

COUCH_CACHE_TIMEOUT = 60 * 60 * 12
MOCK_REDIS_CACHE = None

try:
    REDIS_CACHE = cache.get_cache('redis')
except:
    REDIS_CACHE = None

DEBUG_TRACE = False

CACHE_DOCS = getattr(settings, 'COUCH_CACHE_DOCS', False)
CACHE_VIEWS = getattr(settings, 'COUCH_CACHE_VIEWS', False)


CACHED_VIEW_PREFIX = '#cached_view_'

#the actual payload of the cached_doc
CACHED_DOC_PREFIX = '#cached_doc_'
CACHED_DOC_PROP_PREFIX = '#cached_doc_helper_'

class RedisClientError(Exception):
    pass

def rcache():
    return MOCK_REDIS_CACHE or get_redis_default_cache()


def get_redis_default_cache():
    """
    Get the redis cache, or just the default if it doesn't exist
    """
    try:
        return cache.get_cache('redis')
    except (InvalidCacheBackendError, ValueError):
        return cache.cache


def get_redis_client():
    if not REDIS_CACHE:
        raise RedisClientError("No redis cache defined in settings")

    try:
        try:
            client = REDIS_CACHE.raw_client
        except AttributeError:
            # version >= 3.8.0
            client = REDIS_CACHE.client.get_client()
    except Exception:
        log.error("Could not get redis connection.", exc_info=True)
        raise RedisClientError("Could not get redis connection.")
    return client

def key_doc_prop(doc_id, prop_name):
    return ':'.join([CACHED_DOC_PROP_PREFIX, doc_id, prop_name])


def key_doc_id(doc_id):
    """
    Redis cache key for a full couch document by doc_id
    """
    ret = ":".join([CACHED_DOC_PREFIX, doc_id])
    return ret

# has to be down here because of cyclic dependency
# todo: move all above out of init; this should really be the only thing in init
from .api import *
from .gen import *
from .const import *
