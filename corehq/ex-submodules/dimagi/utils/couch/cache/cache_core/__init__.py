import logging
from django.conf import settings
from django.core import cache
from django.core.cache import InvalidCacheBackendError
from django_redis.cache import RedisCache


log = logging.getLogger(__name__)

COUCH_CACHE_TIMEOUT = 60 * 60 * 12
MOCK_REDIS_CACHE = None

try:
    REDIS_CACHE = cache.caches['redis']
except InvalidCacheBackendError:
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
        return cache.caches['redis']
    except (InvalidCacheBackendError, ValueError):
        return cache.cache


def get_redis_client():
    rcache = get_redis_default_cache()

    if not isinstance(rcache, RedisCache):
        raise RedisClientError('Could not get redis cache. Is the redis cache configured?')

    return rcache


def key_doc_id(doc_id):
    """
    Redis cache key for a full couch document by doc_id
    """
    ret = ":".join([CACHED_DOC_PREFIX, doc_id])
    return ret

# has to be down here because of cyclic dependency
# todo: move all above out of init; this should really be the only thing in init
from .api import *  # noqa: E402
from .gen import *  # noqa: E402
from .const import *  # noqa: E402
