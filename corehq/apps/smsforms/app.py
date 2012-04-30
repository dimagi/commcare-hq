from .models import XFormsSession
from datetime import datetime
from touchforms.formplayer import api
from corehq.apps.cloudcare.touchforms_api import get_session_data
from touchforms.formplayer.api import XFormsConfig

def start_session(domain, contact, app, module, form, case_id=None):
    """
    Starts a session in touchforms and saves the record in the database.
    Returns a tuple of the session object, and the touchforms response
    object.
    """
    # NOTE: this call assumes that "contact" will expose three
    # properties: .raw_username, .get_id, and .get_language_code
    session_data = get_session_data(domain, contact, case_id, 
                                    app.application_version)
    language = contact.get_language_code()
    config = XFormsConfig(form_content=form.render_xform(),
                          language=language,
                          session_data=session_data)
    tf_response = config.start_session()
    
    now = datetime.utcnow()
    
    # just use the contact id as the connection id. may need to revisit this
    connection_id = contact.get_id
    session = XFormsSession(connection_id=connection_id,
                            session_id = tf_response.session_id,
                            start_time=now, modified_time=now, 
                            form_xmlns=form.xmlns,
                            completed=False, domain=domain,
                            app_id=app.get_id, user_id=contact.get_id)
    session.save()
    responses = [r.text_prompt for r in _next(tf_response, session) \
                 if r.text_prompt]
    return responses

def answer_question(session, answer):
    xformsresponse = api.answer_question(session.session_id, _tf_format(answer))
    for resp in _next(xformsresponse, session):
        yield resp

def _next(xformsresponse, session):
    session.modified_time = datetime.utcnow()
    session.save()
    if xformsresponse.is_error:
        yield xformsresponse
    elif xformsresponse.event.type == "question":
        yield xformsresponse
        if xformsresponse.event.datatype == "info":
            # We have to deal with Trigger/Label type messages 
            # expecting an 'ok' type response. So auto-send that 
            # and move on to the next question.
            response = api.answer_question(int(session.session_id),_tf_format('ok'))
            for additional_resp in _next(response, session):
                yield additional_resp
    elif xformsresponse.event.type == "form-complete":
        # TODO: anything else to do here?
        yield xformsresponse

def get_responses(msg):
    """
    Try to process this message like a session-based submission against
    an xform.
    
    Returns a generator of responses if there are any.
    """
    
    # assumes couch_recipient is the connection_id
    session = XFormsSession.view("smsforms/open_sessions_by_connection", 
                                 key=[msg.domain, msg.couch_recipient],
                                 include_docs=True).one()
    if session:
        return [xformsresponse.text_prompt \
                for xformsresponse in answer_question(session, msg.text) \
                if xformsresponse.text_prompt]
                
                
    
def _tf_format(text):
    # touchforms likes ints to be ints so force it if necessary.
    # any additional formatting needs can go here if they come up
    try:
        return int(text)
    except ValueError:
        return text

