import hashlib
from casexml.apps.phone.const import RESTORE_CACHE_KEY_PREFIX, ASYNC_RESTORE_CACHE_KEY_PREFIX
from casexml.apps.phone.utils import get_restore_response_class


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


def restore_payload_path_cache_key(domain, user_id, sync_log_id, device_id):
    return _restore_cache_key(
        domain=domain,
        prefix=RESTORE_CACHE_KEY_PREFIX,
        user_id=user_id,
        version='2.0',
        sync_log_id=sync_log_id,
        device_id=device_id,
    )


def async_restore_task_id_cache_key(domain, user_id, sync_log_id, device_id):
    return _restore_cache_key(
        domain=domain,
        prefix=ASYNC_RESTORE_CACHE_KEY_PREFIX,
        user_id=user_id,
        version=None,
        sync_log_id=sync_log_id,
        device_id=device_id,
    )
