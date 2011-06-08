from datetime import datetime
from django.http import HttpResponse
from django_digest.decorators import *
from casexml.apps.phone import xml
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.caselogic import get_open_cases_to_send
from dimagi.utils.timeout import TimeoutException
import logging
from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase

def generate_restore_payload(user, restore_id):
    
    last_sync = None
    if restore_id:
        try:
            last_sync = SyncLog.get(restore_id)
        except Exception:
            logging.error("Request for bad sync log %s by %s, ignoring..." % (restore_id, user))
    
    cases_to_send = get_open_cases_to_send(user, last_sync)
    case_xml_blocks = [xml.get_case_xml(case, create) for case, create in cases_to_send]
    
    saved_case_ids = [case.case_id for case, _ in cases_to_send]
    last_seq = get_db().info()["update_seq"]
    
    # create a sync log for this
    previous_log_id = last_sync.get_id if last_sync else None
    synclog = SyncLog(user_id=user.userID, last_seq=last_seq,
                      date=datetime.utcnow(), previous_log_id=previous_log_id,
                      cases=saved_case_ids)
    synclog.save()
    
    reg_xml = xml.get_registration_xml(user)
    
    yield xml.get_response("Successfully restored account %s!" % user.raw_username, 
                           xml.RESTOREDATA_TEMPLATE % {"registration": reg_xml, 
                                                       "sync_info": xml.get_sync_xml(synclog.get_id), 
                                                       "case_list": "".join(case_xml_blocks)})

REQUEST_TIMEOUT = 10
#@timeout(REQUEST_TIMEOUT)
def get_full_restore_payload(*args, **kwargs):
    return ''.join(generate_restore_payload(*args, **kwargs))

@httpdigest
def restore(request, domain):
    user = request.user
    restore_id = request.GET.get('since')

    try:
        response = get_full_restore_payload(user, restore_id)
        return HttpResponse(response, mimetype="text/xml")
    except TimeoutException:
        return HttpResponse(status=503)
    

def xml_for_case(request, case_id):
    """
    Test view to get the xml for a particular case
    """
    case = CommCareCase.get(case_id)
    return HttpResponse(xml.get_case_xml(case), mimetype="text/xml")
    