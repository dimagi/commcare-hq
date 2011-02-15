from datetime import datetime
from django.http import HttpResponse
from django_digest.decorators import *
from corehq.apps.phone import xml
from corehq.apps.users import xml as user_xml
from corehq.apps.phone.models import SyncLog, PhoneCase
from django.views.decorators.http import require_POST
from corehq.apps.phone.caselogic import get_open_cases_to_send
from dimagi.utils.timeout import timeout, TimeoutException
import logging
from dimagi.utils.web import render_to_response
from dimagi.utils.couch.database import get_db
from corehq.apps.users.util import couch_user_from_django_user,\
    commcare_account_from_django_user, raw_username
from corehq.apps.users.models import CouchUser


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
        raise Exception("No linked chw found for %s" % username)
    
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
                               

@httpdigest
def test(request, domain):
    """
    Test view
    """
    return HttpResponse(TESTING_RESTORE_DATA, mimetype="text/xml")


TESTING_RESTORE_DATA=\
"""<restoredata> 
<n0:registration xmlns:n0="http://openrosa.org/user-registration">
  <username>bhoma</username>
  <password>234</password>
  <uuid>O9KNJQO8V951GSOXDV7604I1Q</uuid>
  <date>2010-07-28</date>
  <registering_phone_id>SSNCFBLR8U12WB3I8RMKRTACC</registering_phone_id>
  <user_data>
    <data key="providertype">hbcp</data>
    <data key="training">yes</data>
    <data key="sex">m</data>
    <data key="user_type">standard</data>
  </user_data>
</n0:registration>
<case>
<case_id>PZHBCC9647XX0V4YAZ2UUPQ9M</case_id>
<date_modified>2010-07-28T14:49:57.930</date_modified>
<create>
  <case_type_id>bhoma_followup</case_type_id>
  <user_id>O9KNJQO8V951GSOXDV7604I1Q</user_id>
  <case_name>6</case_name>
  <external_id>bhoma8972837492818239</external_id>
</create>
<update>
  <first_name>DREW</first_name>
  <last_name>ROOS</last_name>
  <birth_date>1983-10-06</birth_date>
  <birth_date_est>1</birth_date_est>
  <age>26</age>
  <sex>m</sex>
  <village>SOMERVILLE</village>
  <contact>9183739767</contact>

  <followup_type>missed_appt</followup_type>
  <orig_visit_type>general</orig_visit_type>
  <orig_visit_diagnosis>malaria</orig_visit_diagnosis>
  <orig_visit_date>2010-07-12</orig_visit_date>

  <activation_date>2010-07-27</activation_date>
  <due_date>2010-07-31</due_date>

  <missed_appt_date>2010-07-24</missed_appt_date>
  <ttl_missed_appts>1</ttl_missed_appts>
</update>
</case>

<case>
<case_id>UJ3IN4HBLNTBRNV2SVCE6F5VU</case_id>
<date_modified>2010-07-28T14:49:57.930</date_modified>
<create>

  <case_type_id>bhoma_followup</case_type_id>
  <user_id>O9KNJQO8V951GSOXDV7604I1Q</user_id>
  <case_name>7</case_name>
  <external_id>bhoma20938968738923</external_id>
</create>
<update>
  <first_name>LESTER</first_name>
  <last_name>JENKINS</last_name>
  <birth_date>1934-02-23</birth_date>
  <birth_date_est>0</birth_date_est>
  <age>76</age>
  <sex>m</sex>
  <village>DORCHESTER</village>
  <contact>7814359283</contact>

  <followup_type>hospital</followup_type>
  <orig_visit_type>general</orig_visit_type>
  <orig_visit_diagnosis>pneumonia</orig_visit_diagnosis>
  <orig_visit_date>2010-07-24</orig_visit_date>

  <activation_date>2010-08-03</activation_date>
  <due_date>2010-08-07</due_date>
</update>
</case>

<case>
<case_id>MYTF9AFKZPX8TGYOAXXLUEKCE</case_id>
<date_modified>2010-07-28T14:49:57.930</date_modified>
<create>
  <case_type_id>bhoma_followup</case_type_id>
  <user_id>O9KNJQO8V951GSOXDV7604I1Q</user_id>
  <case_name>8</case_name>
  <external_id>bhoma9989500849805480848</external_id>
</create>
<update>
  <first_name>HEZRAH</first_name>
  <last_name>D'MAGI</last_name>
  <birth_date>2007-11-01</birth_date>
  <birth_date_est>0</birth_date_est>
  <age>2</age>
  <sex>f</sex>
  <village>CHARLESTOWN</village>
  <contact></contact>

  <followup_type>chw_followup</followup_type>
  <orig_visit_type>under_five</orig_visit_type>
  <orig_visit_diagnosis>diarrhea</orig_visit_diagnosis>
  <orig_visit_date>2010-07-31</orig_visit_date>

  <activation_date>2010-08-03</activation_date>
  <due_date>2010-08-07</due_date>
</update>
</case>


</restoredata>
"""
