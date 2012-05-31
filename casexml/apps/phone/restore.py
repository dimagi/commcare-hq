from casexml.apps.phone.models import SyncLog, CaseState
import logging
from dimagi.utils.couch.database import get_db
from casexml.apps.phone import xml
from datetime import datetime
from receiver.xml import get_response_element, get_simple_response_xml,\
    ResponseNature
from casexml.apps.case.xml import check_version
from casexml.apps.phone.fixtures import generator
from django.http import HttpResponse
from casexml.apps.phone.checksum import CaseStateHash

class BadStateException(Exception):
    
    def __init__(self, expected, actual, case_ids, **kwargs):
        super(BadStateException, self).__init__(**kwargs)
        self.expected = expected
        self.actual = actual
        self.case_ids = case_ids
        
    def __str__(self):
        return "Phone state has mismatch. Expected %s but was %s. Cases: [%s]" % \
                (self.expected, self.actual, ", ".join(self.case_ids))
        
        
def generate_restore_payload(user, restore_id="", version="1.0", state_hash=""):
    """
    Gets an XML payload suitable for OTA restore. If you need to do something
    other than find all cases matching user_id = user.user_id then you have
    to pass in a user object that overrides the get_case_updates() method.
    
    It should match the same signature as models.user.get_case_updates():
    
        user:          who the payload is for. must implement get_case_updates
        restore_id:    sync token
        version:       the CommCare version 
        
        returns: the xml payload of the sync operation
    """
    check_version(version)
    
    last_sync = None
    if restore_id:
        try:
            last_sync = SyncLog.get(restore_id)
        except Exception:
            logging.error("Request for bad sync log %s by %s, ignoring..." % (restore_id, user))
    
    if last_sync and state_hash:
        parsed_hash = CaseStateHash.parse(state_hash)
        if last_sync.get_state_hash() != parsed_hash:
            raise BadStateException(expected=last_sync.get_state_hash(), 
                                    actual=parsed_hash,
                                    case_ids=last_sync.get_footprint_of_cases_on_phone())
        
    sync_operation = user.get_case_updates(last_sync)
    case_xml_elements = [xml.get_case_element(op.case, op.required_updates, version) \
                         for op in sync_operation.actual_cases_to_sync]
    
    
    last_seq = get_db().info()["update_seq"]
    
    # create a sync log for this
    previous_log_id = last_sync.get_id if last_sync else None
    
    synclog = SyncLog(user_id=user.user_id, last_seq=last_seq,
                      owner_ids_on_phone=user.get_owner_ids(),
                      date=datetime.utcnow(), previous_log_id=previous_log_id,
                      cases_on_phone=[CaseState.from_case(c) for c in \
                                      sync_operation.actual_owned_cases],
                      dependent_cases_on_phone=[CaseState.from_case(c) for c in \
                                                sync_operation.actual_extended_cases])
    synclog.save()
    
    # start with standard response
    response = get_response_element(
        "Successfully restored account %s!" % user.username, 
        ResponseNature.OTA_RESTORE_SUCCESS)
    
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

    
def generate_restore_response(user, restore_id="", version="1.0", state_hash=""):
    try:
        response = generate_restore_payload(user, restore_id, version, state_hash)
        return HttpResponse(response, mimetype="text/xml")
    except BadStateException, e:
        logging.exception("Bad case state hash submitted by %s: %s" % (user.username, str(e)))
        response = get_simple_response_xml(
            "Phone case list is inconsistant with server's records.",
            ResponseNature.OTA_RESTORE_ERROR)
        return HttpResponse(response, mimetype="text/xml", 
                            status=412) # precondition failed
    