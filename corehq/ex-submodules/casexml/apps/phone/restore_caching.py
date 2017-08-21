import hashlib
import logging
from casexml.apps.phone.const import RESTORE_CACHE_KEY_PREFIX, ASYNC_RESTORE_CACHE_KEY_PREFIX
from casexml.apps.phone.utils import get_restore_response_class
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache

logger = logging.getLogger(__name__)


def _restore_cache_key(domain, prefix, user_id, version, sync_log_id, device_id):
    response_class = get_restore_response_class(domain)
    hashable_key = '{response_class}-{prefix}-{user}-{version}-{sync_log_id}-{device_id}'.format(
        response_class=response_class.__name__,
        prefix=prefix,
        user=user_id,
        version=version or '',
        sync_log_id=sync_log_id or '',
        device_id=device_id or '',
    )
    return hashlib.md5(hashable_key).hexdigest()


def _restore_payload_path_cache_key(domain, user_id, sync_log_id, device_id):
    return _restore_cache_key(
        domain=domain,
        prefix=RESTORE_CACHE_KEY_PREFIX,
        user_id=user_id,
        version='2.0',
        sync_log_id=sync_log_id,
        device_id=device_id,
    )


def _async_restore_task_id_cache_key(domain, user_id, sync_log_id, device_id):
    return _restore_cache_key(
        domain=domain,
        prefix=ASYNC_RESTORE_CACHE_KEY_PREFIX,
        user_id=user_id,
        version=None,
        sync_log_id=sync_log_id,
        device_id=device_id,
    )


class CacheAccessor(object):
    cache_key = None
    timeout = None
    debug_info = None

    def get_value(self):
        logger.debug('getting {}'.format(self.debug_info))
        return get_redis_default_cache().get(self.cache_key)

    def set_value(self, value, timeout=None):
        logger.debug('setting {}'.format(self.debug_info))
        if timeout is None:
            timeout = self.timeout
        get_redis_default_cache().set(self.cache_key, value, timeout=timeout)

    def invalidate(self):
        logger.debug('invalidating {}'.format(self.debug_info))
        get_redis_default_cache().delete(self.cache_key)


class RestorePayloadPathCache(CacheAccessor):
    def __init__(self, domain, user_id, sync_log_id, device_id):
        self.cache_key = _restore_payload_path_cache_key(domain, user_id, sync_log_id, device_id)
        self.debug_info = ('RestorePayloadPathCache', domain, user_id, sync_log_id, device_id)


class AsyncRestoreTaskIdCache(CacheAccessor):
    timeout = 24 * 60 * 60

    def __init__(self, domain, user_id, sync_log_id, device_id):
        self.cache_key = _async_restore_task_id_cache_key(domain, user_id, sync_log_id, device_id)
        self.debug_info = ('AsyncRestoreTaskIdCache', domain, user_id, sync_log_id, device_id)
