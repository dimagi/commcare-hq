from xml.etree import ElementTree
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from casexml.apps.case.xml import V1, V2
from casexml.apps.phone.models import (
    get_properly_wrapped_sync_log,
    get_sync_log_class_by_format,
    OTARestoreWebUser,
    OTARestoreCommCareUser,
)
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings, restore_cache_key
from casexml.apps.phone.tests.dbaccessors import get_all_sync_logs_docs
from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.phone.const import RESTORE_CACHE_KEY_PREFIX

from corehq.apps.users.models import CommCareUser, WebUser


def create_restore_user(
        domain='restore-domain',
        username='mclovin',
        password='***',
        is_mobile_user=True,
        first_name='',
        last_name='',
        phone_number=None):

    user_cls = CommCareUser if is_mobile_user else WebUser
    restore_user_cls = OTARestoreCommCareUser if is_mobile_user else OTARestoreWebUser
    user = restore_user_cls(
        domain,
        user_cls.create(
            domain=domain,
            username=username,
            password=password,
            first_name=first_name,
            user_data={
                'something': 'arbitrary'
            }
        )
    )
    if phone_number:
        user._couch_user.add_phone_number(phone_number)
    return user


def synclog_id_from_restore_payload(restore_payload):
    element = ElementTree.fromstring(restore_payload)
    return element.findall('{%s}Sync' % SYNC_XMLNS)[0].findall('{%s}restore_id' % SYNC_XMLNS)[0].text


def synclog_from_restore_payload(restore_payload):
    return get_properly_wrapped_sync_log(synclog_id_from_restore_payload(restore_payload))


def get_exactly_one_wrapped_sync_log():
    """
    Gets exactly one properly wrapped sync log, or fails hard.
    """
    [doc] = list(get_all_sync_logs_docs())
    return get_sync_log_class_by_format(doc['log_format']).wrap(doc)


def generate_restore_payload(project, user, restore_id="", version=V1, state_hash="",
                             items=False, overwrite_cache=False, force_cache=False):
    """
    Gets an XML payload suitable for OTA restore.

        user:          who the payload is for
        restore_id:    last sync token for this user
        version:       the restore API version

        returns: the xml payload of the sync operation
    """
    return get_restore_config(
        project, user, restore_id, version, state_hash, items, overwrite_cache, force_cache
    ).get_payload().as_string()


def get_restore_config(project, user, restore_id="", version=V1, state_hash="",
                       items=False, overwrite_cache=False, force_cache=False, device_id=None):
    return RestoreConfig(
        project=project,
        restore_user=user,
        params=RestoreParams(
            sync_log_id=restore_id,
            version=version,
            state_hash=state_hash,
            include_item_count=items,
            device_id=device_id,
        ),
        cache_settings=RestoreCacheSettings(
            overwrite_cache=overwrite_cache,
            force_cache=force_cache,
        )
    )


def generate_restore_response(project, user, restore_id="", version=V1, state_hash="", items=False):
    config = RestoreConfig(
        project=project,
        restore_user=user,
        params=RestoreParams(
            sync_log_id=restore_id,
            version=version,
            state_hash=state_hash,
            include_item_count=items
        )
    )
    return config.get_response()


def has_cached_payload(sync_log, version, prefix=RESTORE_CACHE_KEY_PREFIX):
    return bool(get_redis_default_cache().get(restore_cache_key(
        sync_log.domain,
        prefix,
        sync_log.user_id,
        version=version,
        sync_log_id=sync_log._id,
    )))


def call_fixture_generator(gen, restore_user, project=None, last_sync=None, app=None, device_id=''):
    """
    Convenience function for use in unit tests
    """
    from casexml.apps.phone.restore import RestoreState
    from casexml.apps.phone.restore import RestoreParams
    from corehq.apps.domain.models import Domain
    params = RestoreParams(version=V2, app=app, device_id=device_id)
    restore_state = RestoreState(
        project or Domain(name=restore_user.domain),
        restore_user,
        params,
        async=False,
        overwrite_cache=False
    )
    if last_sync:
        params.sync_log_id = last_sync._id
        restore_state._last_sync_log = last_sync
    return gen(restore_state)
