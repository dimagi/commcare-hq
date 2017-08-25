import hashlib
import logging
from casexml.apps.phone.const import RESTORE_CACHE_KEY_PREFIX, ASYNC_RESTORE_CACHE_KEY_PREFIX
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache

logger = logging.getLogger(__name__)


class _CacheAccessor(object):
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


class RestorePayloadPathCache(_CacheAccessor):
    timeout = 24 * 60 * 60

    def __init__(self, domain, user_id, sync_log_id, device_id):
        self.cache_key = self._make_cache_key(domain, user_id, sync_log_id, device_id)
        self.debug_info = ('RestorePayloadPathCache', domain, user_id, sync_log_id, device_id)

    @staticmethod
    def _make_cache_key(domain, user_id, sync_log_id, device_id):
        # to invalidate all restore cache keys, increment the number below
        hashable_key = '0,{prefix},{domain},{user},{sync_log_id},{device_id}'.format(
            domain=domain,
            prefix=RESTORE_CACHE_KEY_PREFIX,
            user=user_id,
            sync_log_id=sync_log_id or '',
            device_id=device_id or '',
        )
        return hashlib.md5(hashable_key).hexdigest()


class AsyncRestoreTaskIdCache(_CacheAccessor):
    timeout = 24 * 60 * 60

    def __init__(self, domain, user_id, sync_log_id, device_id):
        self.cache_key = self._make_cache_key(domain, user_id, sync_log_id, device_id)
        self.debug_info = ('AsyncRestoreTaskIdCache', domain, user_id, sync_log_id, device_id)

    @staticmethod
    def _make_cache_key(domain, user_id, sync_log_id, device_id):
        # to invalidate all restore cache keys, increment the number below
        hashable_key = '0,{prefix},{domain},{user},{sync_log_id},{device_id}'.format(
            domain=domain,
            prefix=ASYNC_RESTORE_CACHE_KEY_PREFIX,
            user=user_id,
            sync_log_id=sync_log_id or '',
            device_id=device_id or '',
        )
        return hashlib.md5(hashable_key).hexdigest()
