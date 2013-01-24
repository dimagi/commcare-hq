import logging
from django.conf import settings

from dimagi.utils.modules import try_import, to_function
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber
from datetime import datetime

from corehq.apps.sms.util import format_message_list
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import _get_responses, start_session
from corehq.apps.app_manager.models import get_app, Form
from casexml.apps.case.models import CommCareCase
from touchforms.formplayer.api import current_question
from dateutil.parser import parse

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
    return send_message_via_backend(msg, onerror=onerror)

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
    return send_message_via_backend(msg, MobileBackend.load(backend_id), onerror=onerror)

def send_message_via_backend(msg, backend=None, onerror=lambda: None):
    """send sms using a specific backend

    msg - outbound message object
    backend - MobileBackend object to use for sending; if None, use the default
      backend guessing rules
    onerror - error handler; mostly useful for logging a custom message to the
      error log
    """
    try:
        if not backend:
            backend = msg.outbound_backend
            # note: this will handle "verified" contacts that are still pending
            # verification, thus the backend is None. it's best to only call
            # send_sms_to_verified_number on truly verified contacts, though

        backend.backend_module.send(msg, **backend.outbound_params)

        try:
            msg.backend_api = backend_module.API_ID
        except Exception:
            pass
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

def incoming(phone_number, text, backend_api, timestamp=None, domain_scope=None):
    """
    entry point for incoming sms

    phone_number - originating phone number
    text - message content
    backend_api - backend ID of receiving sms backend
    timestamp - message received timestamp; defaults to now (UTC)
    domain_scope - if present, only messages from phone numbers that can be
      definitively linked to this domain will be processed; others will be
      dropped (useful to provide security when simulating incoming sms)
    """
    phone_number = clean_phone_number(phone_number)
    v = VerifiedNumber.by_phone(phone_number)
 
    if domain_scope:
        # only process messages for phones known to be associated with this domain
        if v is None or v.domain != domain_scope:
            raise RuntimeError('attempted to simulate incoming sms from phone number not verified with this domain')

    # Log message in message log
    msg = SMSLog(
        phone_number    = phone_number,
        direction       = INCOMING,
        date            = timestamp or datetime.utcnow(),
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
        import verify
        verify.process_verification(phone_number, text)

    return msg

def format_choices(choices_list):
    choices = {}
    for idx, choice in enumerate(choices_list):
        choices[choice.strip().upper()] = idx + 1
    return choices

def form_session_handler(v, text):
    # Circular Import
    from corehq.apps.reminders.models import SurveyKeyword
    
    # Handle incoming sms
    session = XFormsSession.view("smsforms/open_sms_sessions_by_connection",
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
        text = text.strip()
        upper_text = text.upper()
        
        # Validate select
        if event.datatype == "select":
            # Try to match on phrase (i.e., "Yes" or "No")
            choices = format_choices(event._dict["choices"])
            if upper_text in choices:
                text = str(choices[upper_text])
                valid = True
            else:
                try:
                    answer = int(text)
                    if answer >= 1 and answer <= len(event._dict["choices"]):
                        valid = True
                except ValueError:
                    pass
        
        # Validate multiselect
        elif event.datatype == "multiselect":
            choices = format_choices(event._dict["choices"])
            max_index = len(event._dict["choices"])
            proposed_answers = text.split()
            final_answers = {}
            
            try:
                if event._dict.get("required", True):
                    assert len(proposed_answers) > 0
                for answer in proposed_answers:
                    upper_answer = answer.upper()
                    if upper_answer in choices:
                        final_answers[str(choices[upper_answer])] = ""
                    else:
                        int_answer = int(answer)
                        assert int_answer >= 1 and int_answer <= max_index
                        final_answers[str(int_answer)] = ""
                text = " ".join(final_answers.keys())
                valid = True
            except Exception:
                pass
        
        # Validate int
        elif event.datatype == "int":
            try:
                int(text)
                valid = True
            except ValueError:
                pass
        
        # Validate float
        elif event.datatype == "float":
            try:
                float(text)
                valid = True
            except ValueError:
                pass
        
        # Validate longint
        elif event.datatype == "longint":
            try:
                long(text)
                valid = True
            except ValueError:
                pass
        
        # Validate date (Format: YYYYMMDD)
        elif event.datatype == "date":
            try:
                assert len(text) == 8
                int(text)
                text = text[0:4] + "-" + text[4:6] + "-" + text[6:]
                parse(text)
                valid = True
            except Exception:
                pass
        
        # Validate time (Format: HHMM, 24-hour)
        elif event.datatype == "time":
            try:
                assert len(text) == 4
                hour = int(text[0:2])
                minute = int(text[2:])
                assert hour >= 0 and hour <= 23
                assert minute >= 0 and minute <= 59
                text = "%s:%s" % (hour, minute)
                valid = True
            except Exception:
                pass
        
        # Other question types pass
        else:
            valid = True
        
        if valid:
            responses = _get_responses(v.domain, v.owner_id, text)
            if len(responses) > 0:
                response_text = format_message_list(responses)
                send_sms_to_verified_number(v, response_text)
        else:
            error_msg = "Invalid Response. " + event.text_prompt
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

def fallback_handler(v, text):
    send_sms_to_verified_number(v, 'could not understand your message. please check keyword.')
    return True
