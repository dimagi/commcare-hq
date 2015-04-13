from xml.etree import ElementTree
from casexml.apps.case.xml import V1
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.restore import RestoreConfig
from casexml.apps.phone.xml import SYNC_XMLNS


def synclog_id_from_restore_payload(restore_payload):
    try:
        element = ElementTree.parse(restore_payload)
    except IOError:
        element = ElementTree.fromstring(restore_payload)
    return element.findall('{%s}Sync' % SYNC_XMLNS)[0].findall('{%s}restore_id' % SYNC_XMLNS)[0].text


def synclog_from_restore_payload(restore_payload):
    return SyncLog.get(synclog_id_from_restore_payload(restore_payload))


def generate_restore_payload(user, restore_id="", version=V1, state_hash="",
                             items=False):
    """
    Gets an XML payload suitable for OTA restore.

        user:          who the payload is for
        restore_id:    last sync token for this user
        version:       the restore API version

        returns: the xml payload of the sync operation
    """
    config = RestoreConfig(user, restore_id, version, state_hash, items=items)
    return config.get_payload()


def generate_restore_response(user, restore_id="", version=V1, state_hash="",
                              items=False):
    config = RestoreConfig(user, restore_id, version, state_hash, items=items)
    return config.get_response()


