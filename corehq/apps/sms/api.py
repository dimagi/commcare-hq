import logging
from django.conf import settings

from dimagi.utils.modules import to_function
from corehq.apps.sms.util import clean_phone_number, create_billable_for_sms, format_message_list
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING, ForwardingRule, FORWARD_ALL, FORWARD_BY_KEYWORD
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber
from corehq.apps.domain.models import Domain
from datetime import datetime

from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import _get_responses, start_session
from corehq.apps.app_manager.models import Form
from corehq.apps.sms.util import register_sms_contact, strip_plus
from touchforms.formplayer.api import current_question
from dateutil.parser import parse

# A list of all keywords which allow registration via sms.
# Meant to allow support for multiple languages.
# Keywords should be in all caps.
REGISTRATION_KEYWORDS = ["JOIN"]
REGISTRATION_MOBILE_WORKER_KEYWORDS = ["WORKER"]

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

        backend.backend_module.send(msg, **backend.get_cleaned_outbound_params())

        try:
            msg.backend_api = backend.backend_module.API_ID
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
        
    except Exception:
        logging.exception("Exception while starting survey for keyword %s, domain %s" % (survey_keyword.keyword, verified_number.domain))

def process_sms_registration(msg):
    """
    This method handles registration via sms.
    Returns True if a contact was registered, False if not.
    
    To have a case register itself, do the following:

        1) Select "Enable Case Registration Via SMS" in project settings, and fill in the
        associated Case Registration settings.

        2) Text in "join <domain>", where <domain> is the domain to join. If the sending
        number does not exist in the system, a case will be registered tied to that number.
        The "join" keyword can be any keyword in REGISTRATION_KEYWORDS. This is meant to
        support multiple translations.
    
    To have a mobile worker register itself, do the following:

        NOTE: This is not yet implemented and may change slightly.

        1) Select "Enable Mobile Worker Registration via SMS" in project settings.

        2) Text in "join <domain> worker", where <domain> is the domain to join. If the
        sending number does not exist in the system, a PendingCommCareUser object will be
        created, tied to that number.
        The "join" and "worker" keywords can be any keyword in REGISTRATION_KEYWORDS and
        REGISTRATION_MOBILE_WORKER_KEYWORDS, respectively. This is meant to support multiple 
        translations.

        3) A domain admin will have to approve the addition of the mobile worker before
        a CommCareUser can actually be created.
    """
    registration_processed = False
    text_words = msg.text.upper().split()
    keyword1 = text_words[0] if len(text_words) > 0 else ""
    keyword2 = text_words[1].lower() if len(text_words) > 1 else ""
    keyword3 = text_words[2] if len(text_words) > 2 else ""
    if keyword1 in REGISTRATION_KEYWORDS and keyword2 != "":
        domain = Domain.get_by_name(keyword2, strict=True)
        if domain is not None:
            if keyword3 in REGISTRATION_MOBILE_WORKER_KEYWORDS and domain.sms_mobile_worker_registration_enabled:
                #TODO: Register a PendingMobileWorker object that must be approved by a domain admin
                pass
            elif domain.sms_case_registration_enabled:
                register_sms_contact(
                    domain=domain.name,
                    case_type=domain.sms_case_registration_type,
                    case_name="unknown",
                    user_id=domain.sms_case_registration_user_id,
                    contact_phone_number=strip_plus(msg.phone_number),
                    contact_phone_number_is_verified="1",
                    owner_id=domain.sms_case_registration_owner_id,
                )
                msg.domain = domain.name
                msg.save()
                registration_processed = True
    
    return registration_processed

def incoming(phone_number, text, backend_api, timestamp=None, domain_scope=None, delay=True):
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

    create_billable_for_sms(msg, backend_api, delay=delay)
    
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
        if not process_sms_registration(msg):
            import verify
            verify.process_verification(phone_number, text)

    return msg

def format_choices(choices_list):
    choices = {}
    for idx, choice in enumerate(choices_list):
        choices[choice.strip().upper()] = idx + 1
    return choices

def validate_answer(event, text):
    text = text.strip()
    upper_text = text.upper()
    valid = False
    error_msg = ""
    
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
                else:
                    error_msg = "Choice is out of range."
            except ValueError:
                error_msg = "Invalid choice."
    
    # Validate multiselect
    elif event.datatype == "multiselect":
        choices = format_choices(event._dict["choices"])
        max_index = len(event._dict["choices"])
        proposed_answers = text.split()
        final_answers = {}
        
        if event._dict.get("required", True) and len(proposed_answers) == 0:
            error_msg = "At least one choice must be selected."
        else:
            try:
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
                error_msg = "Invalid choice."
    
    # Validate int
    elif event.datatype == "int":
        try:
            int(text)
            valid = True
        except ValueError:
            error_msg = "Invalid integer entered."
    
    # Validate float
    elif event.datatype == "float":
        try:
            float(text)
            valid = True
        except ValueError:
            error_msg = "Invalid floating point number entered."
    
    # Validate longint
    elif event.datatype == "longint":
        try:
            long(text)
            valid = True
        except ValueError:
            error_msg = "Invalid long integer entered."
    
    # Validate date (Format: YYYYMMDD)
    elif event.datatype == "date":
        try:
            assert len(text) == 8
            int(text)
            text = "%s-%s-%s" % (text[0:4], text[4:6], text[6:])
            parse(text)
            valid = True
        except Exception:
            error_msg = "Invalid date format: expected YYYYMMDD."
    
    # Validate time (Format: HHMM, 24-hour)
    elif event.datatype == "time":
        try:
            assert len(text) == 4
            hour = int(text[0:2])
            minute = int(text[2:])
            assert hour >= 0 and hour <= 23
            assert minute >= 0 and minute <= 59
            text = "%s:%s" % (hour, str(minute).zfill(2))
            valid = True
        except Exception:
            error_msg = "Invalid time format: expected HHMM (24-hour)."
    
    # Other question types pass
    else:
        valid = True
    
    return (valid, text, error_msg)

def is_form_complete(current_question):
    # Force a return value of either True or False (instead of None)
    if current_question.event and current_question.event.type == "form-complete":
        return True
    else:
        return False

def close_open_sessions(domain, connection_id):
    sessions = XFormsSession.view("smsforms/open_sms_sessions_by_connection",
                                 key=[domain, connection_id],
                                 include_docs=True).all()
    for session in sessions:
        session.end(False)
        session.save()

def structured_sms_handler(verified_number, text):
    
    # Circular Import
    from corehq.apps.reminders.models import SurveyKeyword, FORM_TYPE_ALL_AT_ONCE
    
    text = text.strip()
    if text == "":
        return False
    for survey_keyword in SurveyKeyword.get_all(verified_number.domain):
        if survey_keyword.form_type == FORM_TYPE_ALL_AT_ONCE:
            if survey_keyword.delimiter is not None:
                args = text.split(survey_keyword.delimiter)
            else:
                args = text.split()
            
            keyword = args[0].strip().upper()
            if keyword != survey_keyword.keyword.upper():
                continue
            
            try:
                error_occurred = False
                error_msg = ""
                form_complete = False
                
                # Close any open sessions
                close_open_sessions(verified_number.domain, verified_number.owner_id)
                
                # Start the session
                form = Form.get_form(survey_keyword.form_unique_id)
                app = form.get_app()
                module = form.get_module()
                
                if verified_number.owner_doc_type == "CommCareCase":
                    case_id = verified_number.owner_id
                else:
                    #TODO: Need a way to choose the case when it's a user that's playing the form
                    case_id = None
                
                session, responses = start_session(verified_number.domain, verified_number.owner, app, module, form, case_id=case_id, yield_responses=True)
                assert len(responses) > 0, "There should be at least one response."
                
                current_question = responses[-1]
                form_complete = is_form_complete(current_question)
                
                if not form_complete:
                    if survey_keyword.use_named_args:
                        # Arguments in the sms are named
                        xpath_answer = {} # Dictionary of {xpath : answer}
                        for answer in args[1:]:
                            answer = answer.strip()
                            answer_upper = answer.upper()
                            if survey_keyword.named_args_separator is not None:
                                # A separator is used for naming arguments; for example, the "=" in "register name=joe age=25"
                                answer_parts = answer.partition(survey_keyword.named_args_separator)
                                if answer_parts[1] != survey_keyword.named_args_separator:
                                    error_occurred = True
                                    error_msg = "ERROR: Expected name and value to be joined by" + (" '%s'" % survey_keyword.named_args_separator)
                                    break
                                else:
                                    arg_name = answer_parts[0].upper().strip()
                                    xpath = survey_keyword.named_args.get(arg_name, None)
                                    if xpath is not None:
                                        if xpath in xpath_answer:
                                            error_occurred = True
                                            error_msg = "ERROR: More than one answer found for" + (" '%s'" % arg_name)
                                            break
                                        
                                        xpath_answer[xpath] = answer_parts[2].strip()
                                    else:
                                        # Ignore unexpected named arguments
                                        pass
                            else:
                                # No separator is used for naming arguments; for example, "update a100 b34 c5"
                                matches = 0
                                for k, v in survey_keyword.named_args.items():
                                    if answer_upper.startswith(k):
                                        matches += 1
                                        if matches > 1:
                                            error_occurred = True
                                            error_msg = "ERROR: More than one question matches" + (" '%s'" % answer)
                                            break
                                        
                                        if v in xpath_answer:
                                            error_occurred = True
                                            error_msg = "ERROR: More than one answer found for" + (" '%s'" % k)
                                            break
                                        
                                        xpath_answer[v] = answer[len(k):].strip()
                                
                                if matches == 0:
                                    # Ignore unexpected named arguments
                                    pass
                            
                            if error_occurred:
                                break
                        
                        # Go through each question in the form, answering only the questions that the sms has answers for
                        while not form_complete and not error_occurred:
                            if current_question.is_error:
                                error_occurred = True
                                error_msg = current_question.text_prompt or "ERROR: Internal server error"
                                break
                            
                            xpath = current_question.event._dict["binding"]
                            if xpath in xpath_answer:
                                valid, answer, _error_msg = validate_answer(current_question.event, xpath_answer[xpath])
                                if not valid:
                                    error_occurred = True
                                    error_msg = "ERROR: " + _error_msg
                                    break
                                responses = _get_responses(verified_number.domain, verified_number.owner_id, answer, yield_responses=True)
                            else:
                                responses = _get_responses(verified_number.domain, verified_number.owner_id, "", yield_responses=True)
                            
                            current_question = responses[-1]
                            if is_form_complete(current_question):
                                form_complete = True
                    else:
                        # Arguments in the sms are not named; pass each argument to each question in order
                        for answer in args[1:]:
                            if form_complete:
                                # Form is complete, ignore remaining answers
                                break
                            
                            if current_question.is_error:
                                error_occurred = True
                                error_msg = current_question.text_prompt or "ERROR: Internal server error"
                                break
                            
                            valid, answer, _error_msg = validate_answer(current_question.event, answer.strip())
                            if not valid:
                                error_occurred = True
                                error_msg = "ERROR: " + _error_msg
                                break
                            
                            responses = _get_responses(verified_number.domain, verified_number.owner_id, answer, yield_responses=True)
                            current_question = responses[-1]
                            form_complete = is_form_complete(current_question)
                        
                        # If the form isn't finished yet but we're out of arguments, try to leave each remaining question blank and continue
                        while not form_complete and not error_occurred:
                            responses = _get_responses(verified_number.domain, verified_number.owner_id, "", yield_responses=True)
                            current_question = responses[-1]
                            
                            if current_question.is_error:
                                error_occurred = True
                                error_msg = current_question.text_prompt or "ERROR: Internal server error"
                            
                            if is_form_complete(current_question):
                                form_complete = True
            except Exception:
                logging.exception("Could not process structured sms for verified number %s, domain %s, keyword %s" % (verified_number._id, verified_number.domain, keyword))
                error_occurred = True
                error_msg = "ERROR: Internal server error"
            
            if error_occurred:
                send_sms_to_verified_number(verified_number, error_msg)
            
            if error_occurred or not form_complete:
                session = XFormsSession.get(session._id)
                session.end(False)
                session.save()
            
            return True
    
    return False

def form_session_handler(v, text):
    # Circular Import
    from corehq.apps.reminders.models import SurveyKeyword, FORM_TYPE_ONE_BY_ONE
    
    # Handle incoming sms
    session = XFormsSession.view("smsforms/open_sms_sessions_by_connection",
                                 key=[v.domain, v.owner_id],
                                 include_docs=True).one()
    
    text_words = text.upper().split()
    
    # Respond to "#START <keyword>" command
    if len(text_words) > 0 and text_words[0] == "#START":
        if len(text_words) > 1:
            sk = SurveyKeyword.get_keyword(v.domain, text_words[1])
            if sk is not None and sk.form_type == FORM_TYPE_ONE_BY_ONE:
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
        valid, text, error_msg = validate_answer(event, text)
        
        if valid:
            responses = _get_responses(v.domain, v.owner_id, text)
            if len(responses) > 0:
                response_text = format_message_list(responses)
                send_sms_to_verified_number(v, response_text)
        else:
            send_sms_to_verified_number(v, error_msg + event.text_prompt)
        
    # Try to match the text against a keyword to start a survey
    elif len(text_words) > 0:
        sk = SurveyKeyword.get_keyword(v.domain, text_words[0])
        if sk is not None and sk.form_type == FORM_TYPE_ONE_BY_ONE:
            start_session_from_keyword(sk, v)

    # TODO should clarify what scenarios this handler actually handles. i.e.,
    # should the error responses instead be handler by some generic error/fallback
    # handler
    return True

def forwarding_handler(v, text):
    rules = ForwardingRule.view("sms/forwarding_rule", key=[v.domain], include_docs=True).all()
    text_words = text.upper().split()
    keyword_to_match = text_words[0] if len(text_words) > 0 else ""
    for rule in rules:
        matches_rule = False
        if rule.forward_type == FORWARD_ALL:
            matches_rule = True
        elif rule.forward_type == FORWARD_BY_KEYWORD:
            matches_rule = (keyword_to_match == rule.keyword.upper())
        
        if matches_rule:
            send_sms_with_backend(v.domain, "+%s" % v.phone_number, text, rule.backend_id)
            return True
    return False

def fallback_handler(v, text):
    send_sms_to_verified_number(v, 'could not understand your message. please check keyword.')
    return True


