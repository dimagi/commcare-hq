from casexml.apps.phone.models import SyncLog
import logging
from dimagi.utils.couch.database import get_db
from casexml.apps.phone import xml
from datetime import datetime
from receiver.xml import get_response_element
from casexml.apps.case import const
from casexml.apps.case.xml import check_version
from casexml.apps.phone.fixtures import generator

def generate_restore_payload(user, restore_id="", version="1.0"):
    """
    Gets an XML payload suitable for OTA restore. If you need to do something
    other than find all cases matching user_id = user.user_id then you have
    to pass in a user object that overrides the get_case_updates() method.
    
    It should match the same signature as models.user.get_case_updates():
    
        user:          who the payload is for. must implement get_case_updates
        restore_id:    sync token
        version:       the CommCare version 
        
        returns: list of (CommCareCase, previously_synced) tuples
    """
    check_version(version)
    
    last_sync = None
    if restore_id:
        try:
            last_sync = SyncLog.get(restore_id)
        except Exception:
            logging.error("Request for bad sync log %s by %s, ignoring..." % (restore_id, user))
    
    cases_to_send = user.get_case_updates(last_sync)
    case_xml_elements = [xml.get_case_element(case, updates, version) for case, updates in cases_to_send]
    
    
    saved_case_ids = [case.case_id for case, updates in cases_to_send \
                      if const.CASE_ACTION_UPDATE in updates]
    
    last_seq = get_db().info()["update_seq"]
    
    # create a sync log for this
    previous_log_id = last_sync.get_id if last_sync else None
    synclog = SyncLog(user_id=user.user_id, last_seq=last_seq,
                      date=datetime.utcnow(), previous_log_id=previous_log_id,
                      cases=saved_case_ids)
    synclog.save()
    
    # start with standard response
    response = get_response_element("Successfully restored account %s!" % user.username)
    
    # add sync token info
    response.append(xml.get_sync_element(synclog.get_id))
    # registration block
    response.append(xml.get_registration_element(user))
    # fixture block
    for fixture in generator.get_fixtures(user, version, last_sync):
        response.append(fixture)
    # case blocks
    for case_elem in case_xml_elements:
        response.append(case_elem)
    
    return xml.tostring(response)
    
