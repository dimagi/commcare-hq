from xml.etree import ElementTree
from casexml.apps.case.xml import V1
from casexml.apps.phone.models import (
    get_properly_wrapped_sync_log,
    get_sync_log_class_by_format,
    OTARestoreWebUser,
    OTARestoreCommCareUser,
)
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings
from casexml.apps.phone.tests.dbaccessors import get_all_sync_logs_docs
from casexml.apps.phone.xml import SYNC_XMLNS

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
                       items=False, overwrite_cache=False, force_cache=False):
    return RestoreConfig(
        project=project,
        restore_user=user,
        params=RestoreParams(
            sync_log_id=restore_id,
            version=version,
            state_hash=state_hash,
            include_item_count=items
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


def has_cached_payload(sync_log, version):
    return bool(sync_log.get_cached_payload(version))
