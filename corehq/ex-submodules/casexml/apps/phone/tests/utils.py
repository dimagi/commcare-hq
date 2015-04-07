from xml.etree import ElementTree
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.xml import SYNC_XMLNS


def synclog_id_from_restore_payload(restore_payload):
    try:
        element = ElementTree.parse(restore_payload)
    except IOError:
        element = ElementTree.fromstring(restore_payload)
    return element.findall('{%s}Sync' % SYNC_XMLNS)[0].findall('{%s}restore_id' % SYNC_XMLNS)[0].text

def synclog_from_restore_payload(restore_payload):
    return SyncLog.get(synclog_id_from_restore_payload(restore_payload))

