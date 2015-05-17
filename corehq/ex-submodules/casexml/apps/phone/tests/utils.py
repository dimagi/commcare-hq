import warnings
from xml.etree import ElementTree
from casexml.apps.case.tests import TEST_DOMAIN_NAME
from casexml.apps.case.xml import V1
from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_all_sync_logs_docs
from casexml.apps.phone.models import get_properly_wrapped_sync_log, get_sync_log_class_by_format
from casexml.apps.phone.restore import RestoreConfig, RestoreParams, RestoreCacheSettings
from casexml.apps.phone.xml import SYNC_XMLNS
from corehq.apps.domain.models import Domain


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


def generate_restore_payload(user, restore_id="", version=V1, state_hash="",
                             items=False, overwrite_cache=False, force_cache=False):
    """
    Gets an XML payload suitable for OTA restore.

        user:          who the payload is for
        restore_id:    last sync token for this user
        version:       the restore API version

        returns: the xml payload of the sync operation
    """
    warnings.warn(
        'This function is deprecated. You should be using generate_restore_payload_with_project.',
        DeprecationWarning,
    )
    return generate_restore_payload_with_project(
        Domain(name=user.domain or TEST_DOMAIN_NAME),
        user, restore_id, version, state_hash, items, overwrite_cache, force_cache
    )


def generate_restore_payload_with_project(project, user, restore_id="", version=V1, state_hash="",
                                 items=False, overwrite_cache=False, force_cache=False):
    config = RestoreConfig(
        project=project,
        user=user,
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
    return config.get_payload().as_string()


def generate_restore_response(user, restore_id="", version=V1, state_hash="",
                              items=False):
    config = RestoreConfig(
        user=user,
        params=RestoreParams(
            sync_log_id=restore_id,
            version=version,
            state_hash=state_hash,
            include_item_count=items
        )
    )
    return config.get_response()
