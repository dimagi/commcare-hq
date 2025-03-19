import datetime
import hashlib
import logging

from dimagi.utils.couch.cache.cache_core import get_redis_default_cache

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.util.quickcache import quickcache

from .const import ASYNC_RESTORE_CACHE_KEY_PREFIX, RESTORE_CACHE_KEY_PREFIX

logger = logging.getLogger(__name__)


class _CacheAccessor(object):
    cache_key = None
    timeout = None
    debug_info = None

    def exists(self):
        logger.debug('if exists {}'.format(self.debug_info))
        return self.cache_key in get_redis_default_cache()

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


@quickcache(['domain', 'user_id'], timeout=24 * 60 * 60)
def get_loadtest_factor_for_restore_cache_key(domain, user_id):
    from corehq.apps.users.models import CouchUser, CommCareUser
    if domain_has_privilege(domain, privileges.LOADTEST_USERS) and user_id:
        user = CouchUser.get_by_user_id(user_id, domain=domain)
        if isinstance(user, CommCareUser):
            return user.loadtest_factor or 1
    return 1


def _get_new_arbitrary_value():
    # a random value would work here, but this leaves a more useful trail for debugging
    return datetime.datetime.utcnow().isoformat()


@quickcache(['domain'], timeout=60 * 24 * 60 * 60)
def _get_domain_freshness_token(domain):
    return _get_new_arbitrary_value()


@quickcache(['domain', 'user_id'], timeout=60 * 24 * 60 * 60)
def _get_user_freshness_token(domain, user_id):
    return _get_new_arbitrary_value()


def invalidate_restore_cache(domain, user_id=Ellipsis):
    assert domain
    if user_id is not Ellipsis:
        assert user_id
        _get_user_freshness_token.clear(domain, user_id)
    else:
        _get_domain_freshness_token.clear(domain)


class _RestoreCache(_CacheAccessor):
    prefix = None

    def __init__(self, domain, user_id, sync_log_id, device_id):
        self.cache_key = self._make_cache_key(domain, user_id, sync_log_id, device_id)
        self.debug_info = (self.__class__.__name__, domain, user_id, sync_log_id, device_id)

    @classmethod
    def _make_cache_key(cls, domain, user_id, sync_log_id, device_id):
        hashable_key = ','.join([str(part) for part in [
            domain,
            cls.prefix,
            user_id,
            sync_log_id or '',
            device_id or '',
            get_loadtest_factor_for_restore_cache_key(domain, user_id),
            _get_domain_freshness_token(domain),
            _get_user_freshness_token(domain, user_id),
        ]])
        return hashlib.md5(hashable_key.encode('utf-8')).hexdigest()


class RestorePayloadPathCache(_RestoreCache):
    timeout = 24 * 60 * 60
    prefix = RESTORE_CACHE_KEY_PREFIX


class AsyncRestoreTaskIdCache(_RestoreCache):
    timeout = 24 * 60 * 60
    prefix = ASYNC_RESTORE_CACHE_KEY_PREFIX
