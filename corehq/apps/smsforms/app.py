from .models import XFormsSession
from datetime import datetime
from corehq.apps.cloudcare.touchforms_api import get_session_data
from touchforms.formplayer.api import XFormsConfig, DigestAuth
from touchforms.formplayer import sms as tfsms
from django.conf import settings

COMMCONNECT_DEVICE_ID = "commconnect"

AUTH = DigestAuth(settings.TOUCHFORMS_API_USER, 
                  settings.TOUCHFORMS_API_PASSWORD)

def start_session(domain, contact, app, module, form, case_id=None):
    """
    Starts a session in touchforms and saves the record in the database.
    
    Returns a tuple containing the session object and the (text-only) 
    list of generated questions/responses based on the form.
    """
    # NOTE: this call assumes that "contact" will expose three
    # properties: .raw_username, .get_id, and .get_language_code
    session_data = get_session_data(domain, contact, case_id, 
                                    version=app.application_version, 
                                    device_id=COMMCONNECT_DEVICE_ID)
    
    # since the API user is a superuser, force touchforms to query only
    # the contact's cases by specifying it as an additional filterp
    if contact.doc_type == "CommCareCase":
        session_data["additional_filters"] = { "case_id": contact.get_id }
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
    session_id, responses = tfsms.start_session(config)
    session = XFormsSession(connection_id=connection_id,
                            session_id = session_id,
                            start_time=now, modified_time=now, 
                            form_xmlns=form.xmlns,
                            completed=False, domain=domain,
                            app_id=app.get_id, user_id=contact.get_id)
    session.save()
    return (session, _responses_to_text(responses))

def get_responses(msg):
    return get_responses(msg.domain, msg.couch_recipient, msg.text)

def _get_responses(domain, recipient, text):
    """
    Try to process this message like a session-based submission against
    an xform.
    
    Returns a list of responses if there are any.
    """
        # assumes couch_recipient is the connection_id
    session = XFormsSession.view("smsforms/open_sessions_by_connection", 
                                 key=[domain, recipient],
                                 include_docs=True).one()
    if session:
        session.modified_time = datetime.utcnow()
        session.save()
        # TODO auth
        return _responses_to_text(tfsms.next_responses(session.session_id, text,
                                                       auth=None))
                
def _responses_to_text(responses):
    return [r.text_prompt for r in responses if r.text_prompt]
