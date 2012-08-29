import logging
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber
from datetime import datetime
from corehq.apps.unicel import api as unicel_api

from corehq.apps.tropo import api as tropo_api
from corehq.apps.sms import mach_api
from corehq.apps.sms.util import format_message_list
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import get_responses, start_session
from corehq.apps.app_manager.models import get_app, Form
from casexml.apps.case.models import CommCareCase
from touchforms.formplayer.api import current_question

ALTERNATIVE_BACKENDS = [("+91", unicel_api)] # TODO: move to setting?
DEFAULT_BACKEND = mach_api

def get_backend_api(msg):
    """
    Given a message, find which version of the api to return.
    """
    # this is currently a very dumb method that checks for 
    # india and routes to unicel, otherwise returning mach
    
    # The caller assumes the returned module has a send() method 
    # that takes in a message object.
    phone = clean_phone_number(msg.phone_number)
    for code, be_module in ALTERNATIVE_BACKENDS:
        if phone.startswith(code):
            return be_module
    return DEFAULT_BACKEND

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
    msg = SMSLog(domain=domain,
                     couch_recipient=id, 
                     couch_recipient_doc_type="CouchUser",
                     phone_number=phone_number,
                     direction=OUTGOING,
                     date = datetime.utcnow(),
                     text = text)
    try:
        api = get_backend_api(msg)
        try:
            msg.backend_api = api.API_ID
        except Exception:
            pass
        api.send(msg)
        msg.save()
        return True
    except Exception:
        logging.exception("Problem sending SMS to %s" % phone_number)
        return False

def send_sms_to_verified_number(verified_number, text):
    """
    Sends an sms using the given verified phone number entry.
    
    verified_number The VerifiedNumber entry to use when sending.
    text            The text of the message to send.
    
    return  True on success, False on failure
    """
    try:
        backend = verified_number.backend
        module = __import__(backend.outbound_module, fromlist=["send"])
        kwargs = backend.outbound_params
        msg = SMSLog(
            couch_recipient_doc_type    = verified_number.owner_doc_type,
            couch_recipient             = verified_number.owner_id,
            phone_number                = "+" + str(verified_number.phone_number),
            direction                   = OUTGOING,
            date                        = datetime.utcnow(),
            domain                      = verified_number.domain,
            text                        = text
        )
        try:
            msg.backend_api = module.API_ID
        except Exception:
            pass
        module.send(msg, **kwargs)
        msg.save()
        return True
    except Exception as e:
        logging.exception("Exception while sending SMS to VerifiedNumber id " + verified_number._id)
        return False

def send_sms_with_backend(domain, phone_number, text, backend_id):
    msg = SMSLog(domain = domain,
                 phone_number = phone_number,
                 direction = OUTGOING,
                 date = datetime.utcnow(),
                 text = text)
    if backend_id == "MOBILE_BACKEND_MACH":
        try:
            try:
                msg.backend_api = mach_api.API_ID
            except Exception:
                pass
            mach_api.send(msg)
            msg.save()
            return True
        except Exception:
            logging.exception("Exception while sending SMS to %s with backend %s" % (phone_number, backend_id))
            return False
    elif backend_id == "MOBILE_BACKEND_UNICEL":
        try:
            try:
                msg.backend_api = unicel_api.API_ID
            except Exception:
                pass
            unicel_api.send(msg)
            msg.save()
            return True
        except Exception:
            logging.exception("Exception while sending SMS to %s with backend %s" % (phone_number, backend_id))
            return False
    else:
        try:
            backend = MobileBackend.get(backend_id)
        except Exception:
            backend = None
        if backend is None:
            return False
        
        try:
            module = __import__(backend.outbound_module, fromlist=["send"])
            try:
                msg.backend_api = module.API_ID
            except Exception:
                pass
            kwargs = backend.outbound_params
            module.send(msg, **kwargs)
            msg.save()
            return True
        except Exception as e:
            logging.exception("Exception while sending SMS to %s with backend %s" % (phone_number, backend_id))
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
    
    # Circular Import
    from corehq.apps.reminders.models import SurveyKeyword
    
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
    
    # Handle incoming sms
    if v is not None:
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
                responses = get_responses(msg)
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
    else:
        #TODO: Registration via SMS
        pass



