from .models import XFormsSession, XFORMS_SESSION_SMS
from datetime import datetime
from corehq.apps.cloudcare.touchforms_api import get_session_data
from touchforms.formplayer.api import XFormsConfig, DigestAuth, get_raw_instance
from touchforms.formplayer import sms as tfsms
from django.conf import settings
from xml.etree.ElementTree import XML, tostring
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.receiverwrapper.util import get_submit_url
from receiver.util import spoof_submission
from couchforms.models import XFormInstance
import re

COMMCONNECT_DEVICE_ID = "commconnect"

AUTH = DigestAuth(settings.TOUCHFORMS_API_USER, 
                  settings.TOUCHFORMS_API_PASSWORD)

def start_session(domain, contact, app, module, form, case_id=None, yield_responses=False, session_type=XFORMS_SESSION_SMS, case_for_case_submission=False):
    """
    Starts a session in touchforms and saves the record in the database.
    
    Returns a tuple containing the session object and the (text-only) 
    list of generated questions/responses based on the form.
    
    Special params:
    yield_responses - If True, the list of xforms responses is returned, otherwise the text prompt for each is returned
    session_type - XFORMS_SESSION_SMS or XFORMS_SESSION_IVR
    case_for_case_submission - True if this is a submission that a case is making to alter another related case. For example, if a parent case is filling out
        an SMS survey which will update its child case, this should be True.
    """
    # NOTE: this call assumes that "contact" will expose three
    # properties: .raw_username, .get_id, and .get_language_code
    session_data = get_session_data(domain, contact, case_id, device_id=COMMCONNECT_DEVICE_ID)
    
    # since the API user is a superuser, force touchforms to query only
    # the contact's cases by specifying it as an additional filterp
    if contact.doc_type == "CommCareCase":
        session_data["additional_filters"] = {
            "case_id": contact.get_id,
            "footprint" : "True",
            "include_children" : "True" if case_for_case_submission else "False",
        }
    else:
        session_data["additional_filters"] = { "user_id": contact.get_id }
    
    language = contact.get_language_code()
    config = XFormsConfig(form_content=form.render_xform(),
                          language=language,
                          session_data=session_data,
                          auth=AUTH)
    
    
    now = datetime.utcnow()
    # just use the contact id as the connection id. may need to revisit this
    connection_id = contact.get_id
    session_start_info = tfsms.start_session(config)
    session = XFormsSession(connection_id=connection_id,
                            session_id = session_start_info.session_id,
                            start_time=now, modified_time=now, 
                            form_xmlns=form.xmlns,
                            completed=False, domain=domain,
                            app_id=app.get_id, user_id=contact.get_id,
                            session_type=session_type)
    session.save()
    responses = session_start_info.first_responses
    # Prevent future resource conflicts by getting the session again from the db
    # since the session could have been updated separately in the first_responses call
    session = XFormsSession.get(session._id)
    if yield_responses:
        return (session, responses)
    else:
        return (session, _responses_to_text(responses))

def get_responses(msg):
    return _get_responses(msg.domain, msg.couch_recipient, msg.text)

def _get_responses(domain, recipient, text, yield_responses=False, session_id=None):
    """
    Try to process this message like a session-based submission against
    an xform.
    
    Returns a list of responses if there are any.
    """
        # assumes couch_recipient is the connection_id
    if session_id is not None:
        session = XFormsSession.latest_by_session_id(session_id)
    else:
        # The IVR workflow passes the session id, the SMS workflow grabs the open sms session
        session = XFormsSession.view("smsforms/open_sms_sessions_by_connection", 
                                     key=[domain, recipient],
                                     include_docs=True).one()
    if session:
        session.modified_time = datetime.utcnow()
        session.save()
        # TODO auth
        if yield_responses:
            return list(tfsms.next_responses(session.session_id, text, auth=None))
        else:
            return _responses_to_text(tfsms.next_responses(session.session_id, text, auth=None))

def _responses_to_text(responses):
    return [r.text_prompt for r in responses if r.text_prompt]

"""
Gets the raw instance of the session's form and submits it. This is used with
sms and ivr surveys to save all questions answered so far in a session that 
needs to close.

If include_case_side_effects is False, no case create / update / close actions
will be performed, but the form will still be submitted.

The form is only submitted if the smsforms session has not yet completed.
"""
def submit_unfinished_form(session_id, include_case_side_effects=False):
    session = XFormsSession.latest_by_session_id(session_id)
    if session is not None and session.end_time is None:
        # Get and clean the raw xml
        xml = get_raw_instance(session_id)
        root = XML(xml)
        case_tag_regex = re.compile("^(\{.*\}){0,1}case$") # Use regex in order to search regardless of namespace
        meta_tag_regex = re.compile("^(\{.*\}){0,1}meta$")
        timeEnd_tag_regex = re.compile("^(\{.*\}){0,1}timeEnd$")
        current_timstamp = json_format_datetime(datetime.utcnow())
        for child in root:
            if case_tag_regex.match(child.tag) is not None:
                # Found the case tag
                case_element = child
                case_element.set("date_modified", current_timstamp)
                if not include_case_side_effects:
                    # Remove case actions (create, update, close)
                    child_elements = [case_action for case_action in case_element]
                    for case_action in child_elements:
                        case_element.remove(case_action)
            elif meta_tag_regex.match(child.tag) is not None:
                # Found the meta tag, now set the value for timeEnd
                for meta_child in child:
                    if timeEnd_tag_regex.match(meta_child.tag):
                        meta_child.text = current_timstamp
        cleaned_xml = tostring(root)
        
        # Submit the xml and end the session
        resp = spoof_submission(get_submit_url(session.domain, session.app_id), cleaned_xml, hqsubmission=False)
        xform_id = resp['X-CommCareHQ-FormID']
        session.end(completed=False)
        session.submission_id = xform_id
        session.save()
        
        # Tag the submission as a partial submission
        xform = XFormInstance.get(xform_id)
        xform.partial_submission = True
        xform.survey_incentive = session.survey_incentive
        xform.save()


