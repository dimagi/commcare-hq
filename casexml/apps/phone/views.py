from datetime import datetime
from django.http import HttpResponse
from django_digest.decorators import *
from corehq.apps.phone import xml
from corehq.apps.users import xml as user_xml
from corehq.apps.phone.models import SyncLog
from django.views.decorators.http import require_POST
from corehq.apps.phone.caselogic import get_open_cases_to_send
from dimagi.utils.timeout import timeout, TimeoutException
import logging
from dimagi.utils.web import render_to_response
from dimagi.utils.couch.database import get_db
from corehq.apps.users.util import couch_user_from_django_user,\
    commcare_account_from_django_user, raw_username
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase


def generate_restore_payload(user, restore_id):
    last_sync = None
    if restore_id:
        try:
            last_sync = SyncLog.get(restore_id)
        except Exception:
            logging.error("Request for bad sync log %s by %s, ignoring..." % (restore_id, user))
    
    username = user.username
    couch_user = couch_user_from_django_user(user)
    commcare_account = commcare_account_from_django_user(user)
    
    if not couch_user.commcare_accounts:
        response = HttpResponse("No linked chw found for %s" % username)
        response.status_code = 401 # Authentication Failure
        yield response
        return

    
    last_sync_id = 0 if not last_sync else last_sync.last_seq
    
    cases_to_send = get_open_cases_to_send(couch_user.commcare_accounts, last_sync)
    case_xml_blocks = [xml.get_case_xml(case, create) for case, create in cases_to_send]
    
    # save the case blocks
    for case, _ in cases_to_send:
        case.save()
    
    saved_case_ids = [case.case_id for case, _ in cases_to_send]
    last_seq = get_db().info()["update_seq"]
    # create a sync log for this
    if last_sync == None:
        reg_xml = user_xml.get_registration_xml(couch_user)
        synclog = SyncLog(user_id=commcare_account.login_id, last_seq=last_seq,
                          date=datetime.utcnow(), previous_log_id=None,
                          cases=saved_case_ids)
        synclog.save()
    else:
        reg_xml = "" # don't sync registration after initial sync
        synclog = SyncLog(user_id=commcare_account.login_id, last_seq=last_seq,
                          date=datetime.utcnow(),
                          previous_log_id=last_sync.get_id,
                          cases=saved_case_ids)
        synclog.save()
                                         
    yield xml.get_response("Successfully restored account %s!" % raw_username(user.username), 
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
    
def logs(request):
    # TODO: pagination, etc.
    logs = get_db().view("phone/sync_logs_by_chw", group=True, group_level=1).all()
    for log in logs:
        [chw_id] = log["key"]
        chw = CommunityHealthWorker.get(chw_id)
        log["chw"] = chw
        # get last sync:
        log["last_sync"] = SyncLog.last_for_chw(chw_id)
                                  
    return render_to_response(request, "phone/sync_logs.html", 
                              {"sync_data": logs})

def logs_for_chw(request, chw_id):
    chw = CommunityHealthWorker.get(chw_id)
    return render_to_response(request, "phone/sync_logs_for_chw.html", 
                              {"chw": chw })
                               

def xml_for_case(request, domain, case_id):
    """
    Test view to get the xml for a particular case
    """
    case = CommCareCase.get(case_id)
    return HttpResponse(xml.get_case_xml(case), mimetype="text/xml")
    