import logging
from django.conf import settings

from dimagi.utils.modules import try_import, to_function
from corehq.apps.sms.util import clean_phone_number, load_backend
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber
from datetime import datetime

from corehq.apps.sms.util import format_message_list
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import _get_responses, start_session
from corehq.apps.app_manager.models import get_app, Form
from casexml.apps.case.models import CommCareCase
from touchforms.formplayer.api import current_question

def send_sms(domain, id, phone_number, text):
    """
    Sends an outbound SMS. Returns false if it fails.
    """
    if phone_number is None:
        return False
    if isinstance(phone_number, int) or isinstance(phone_number, long):
        phone_number = str(phone_number)
    logging.debug('Sending message: %s' % text)
    phone_number = clean_phone_number(phone_number)

    msg = SMSLog(
        domain=domain,
        couch_recipient=id, 
        couch_recipient_doc_type="CouchUser",
        phone_number=phone_number,
        direction=OUTGOING,
        date = datetime.utcnow(),
        text = text
    )
    
    def onerror():
        logging.exception("Problem sending SMS to %s" % phone_number)
    return send_message_via_backend(msg, msg.outbound_backend, onerror=onerror)

def send_sms_to_verified_number(verified_number, text):
    """
    Sends an sms using the given verified phone number entry.
    
    verified_number The VerifiedNumber entry to use when sending.
    text            The text of the message to send.
    
    return  True on success, False on failure
    """
    msg = SMSLog(
        couch_recipient_doc_type    = verified_number.owner_doc_type,
        couch_recipient             = verified_number.owner_id,
        phone_number                = "+" + str(verified_number.phone_number),
        direction                   = OUTGOING,
        date                        = datetime.utcnow(),
        domain                      = verified_number.domain,
        text                        = text
    )

    def onerror():
        logging.exception("Exception while sending SMS to VerifiedNumber id " + verified_number._id)
    return send_message_via_backend(msg, verified_number.backend, onerror=onerror)

def send_sms_with_backend(domain, phone_number, text, backend_id):
    msg = SMSLog(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=datetime.utcnow(),
        text=text
    )

    def onerror():
        logging.exception("Exception while sending SMS to %s with backend %s" % (phone_number, backend_id))
    return send_message_via_backend(msg, load_backend(backend_id), onerror=onerror)

def send_message_via_backend(msg, backend, onerror=lambda: None):
    try:
        backend_module = try_import(backend.outbound_module)
        try:
            msg.backend_api = backend_module.API_ID
        except Exception:
            pass
        backend_module.send(msg, **backend.outbound_params)
        msg.save()
        return True
    except Exception:
        onerror()
        return False


def start_session_from_keyword(survey_keyword, verified_number):
    try:
        form_unique_id = survey_keyword.form_unique_id
        form = Form.get_form(form_unique_id)
        app = form.get_app()
        module = form.get_module()
        
        if verified_number.owner_doc_type == "CommCareCase":
            case_id = verified_number.owner_id
        else:
            #TODO: Need a way to choose the case when it's a user that's playing the form
            case_id = None
        
        session, responses = start_session(verified_number.domain, verified_number.owner, app, module, form, case_id)
        
        if len(responses) > 0:
            message = format_message_list(responses)
            send_sms_to_verified_number(verified_number, message)
        
    except Exception as e:
        print e
        print "ERROR: Exception raised while starting survey for keyword " + survey_keyword.keyword + ", domain " + verified_number.domain

def incoming(phone_number, text, backend_api):
    phone_without_plus = str(phone_number)
    if phone_without_plus[0] == "+":
        phone_without_plus = phone_without_plus[1:]
    phone_with_plus = "+" + phone_without_plus
    
    v = VerifiedNumber.view("sms/verified_number_by_number",
        key=phone_without_plus,
        include_docs=True
    ).one()
    
    # Log message in message log
    msg = SMSLog(
        phone_number    = phone_with_plus,
        direction       = INCOMING,
        date            = datetime.utcnow(),
        text            = text,
        backend_api     = backend_api
    )
    if v is not None:
        msg.couch_recipient_doc_type    = v.owner_doc_type
        msg.couch_recipient             = v.owner_id
        msg.domain                      = v.domain
    msg.save()
    
    if v is not None:
        for h in settings.SMS_HANDLERS:
            try:
                handler = to_function(h)
            except:
                logging.exception('error loading sms handler: %s' % h)
                continue

            try:
                was_handled = handler(v, text)
            except:
                logging.exception('unhandled error in sms handler %s for message [%s]' % (h, text))
                was_handled = False

            if was_handled:
                break

    else:
        # don't handle messages from unknown phone #s currently
        # TODO support sms registration workflows here
        pass


def form_session_handler(v, text):
    # Circular Import
    from corehq.apps.reminders.models import SurveyKeyword
    
    # Handle incoming sms
    session = XFormsSession.view("smsforms/open_sessions_by_connection",
                                 key=[v.domain, v.owner_id],
                                 include_docs=True).one()
        
    text_words = text.upper().split()
        
    # Respond to "#START <keyword>" command
    if len(text_words) > 0 and text_words[0] == "#START":
        if len(text_words) > 1:
            sk = SurveyKeyword.get_keyword(v.domain, text_words[1])
            if sk is not None:
                if session is not None:
                    session.end(False)
                    session.save()
                start_session_from_keyword(sk, v)
            else:
                send_sms_to_verified_number(v, "Survey '" + text_words[1] + "' not found.")
        else:
            send_sms_to_verified_number(v, "Usage: #START <keyword>")
        
    # Respond to "#STOP" keyword
    elif len(text_words) > 0 and text_words[0] == "#STOP":
        if session is not None:
            session.end(False)
            session.save()
        
    # Respond to "#CURRENT" keyword
    elif len(text_words) > 0 and text_words[0] == "#CURRENT":
        if session is not None:
            resp = current_question(session.session_id)
            send_sms_to_verified_number(v, resp.event.text_prompt)
        
    # Respond to unknown command
    elif len(text_words) > 0 and text_words[0][0] == "#":
        send_sms_to_verified_number(v, "Unknown command '" + text_words[0] + "'")
        
    # If there's an open session, treat the inbound text as the answer to the next question
    elif session is not None:
        resp = current_question(session.session_id)
        event = resp.event
        valid = False
        error_msg = None
            
        # Validate select questions
        if event.datatype == "select":
            try:
                answer = int(text.strip())
                if answer >= 1 and answer <= len(event._dict["choices"]):
                    valid = True
            except Exception:
                pass
            if not valid:
                error_msg = "Invalid Response. " + event.text_prompt
            
        # For now, anything else passes
        else:
            valid = True
            
        if valid:
            responses = _get_responses(v.domain, v.owner_id, text)
            if len(responses) > 0:
                response_text = format_message_list(responses)
                send_sms_to_verified_number(v, response_text)
        else:
            send_sms_to_verified_number(v, error_msg)
        
    # Try to match the text against a keyword to start a survey
    elif len(text_words) > 0:
        sk = SurveyKeyword.get_keyword(v.domain, text_words[0])
        if sk is not None:
            start_session_from_keyword(sk, v)

    # TODO should clarify what scenarios this handler actually handles. i.e.,
    # should the error responses instead be handler by some generic error/fallback
    # handler
    return True
