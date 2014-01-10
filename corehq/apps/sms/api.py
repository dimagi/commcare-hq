import logging
from django.conf import settings
from celery.task import task

from dimagi.utils.modules import to_function
from corehq.apps.sms.util import clean_phone_number, create_billable_for_sms, format_message_list, clean_text
from corehq.apps.sms.models import SMSLog, OUTGOING, INCOMING, ForwardingRule, FORWARD_ALL, FORWARD_BY_KEYWORD, WORKFLOW_KEYWORD
from corehq.apps.sms.mixin import MobileBackend, VerifiedNumber
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.domain.models import Domain
from datetime import datetime

from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import _get_responses, start_session
from corehq.apps.app_manager.models import Form
from corehq.apps.sms.util import register_sms_contact, strip_plus
from corehq.apps.reminders.util import create_immediate_reminder
from touchforms.formplayer.api import current_question
from dateutil.parser import parse
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.groups.models import Group

# A list of all keywords which allow registration via sms.
# Meant to allow support for multiple languages.
# Keywords should be in all caps.
REGISTRATION_KEYWORDS = ["JOIN"]
REGISTRATION_MOBILE_WORKER_KEYWORDS = ["WORKER"]

class DomainScopeValidationError(Exception):
    pass

class BackendAuthorizationException(Exception):
    pass

def add_msg_tags(msg, *args, **kwargs):
    msg.workflow = kwargs.get("workflow", None)
    msg.xforms_session_couch_id = kwargs.get("xforms_session_couch_id", None)
    msg.reminder_id = kwargs.get("reminder_id", None)
    msg.chat_user_id = kwargs.get("chat_user_id", None)

def send_sms(domain, contact, phone_number, text, **kwargs):
    """
    Sends an outbound SMS. Returns false if it fails.
    """
    if phone_number is None:
        return False
    if isinstance(phone_number, int) or isinstance(phone_number, long):
        phone_number = str(phone_number)
    phone_number = clean_phone_number(phone_number)

    msg = SMSLog(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date = datetime.utcnow(),
        backend_id=None,
        text = text
    )
    if contact:
        msg.couch_recipient = contact._id
        msg.couch_recipient_doc_type = contact.doc_type
    add_msg_tags(msg, **kwargs)
    
    def onerror():
        logging.exception("Problem sending SMS to %s" % phone_number)
    return queue_outgoing_sms(msg, onerror=onerror)

def send_sms_to_verified_number(verified_number, text, **kwargs):
    """
    Sends an sms using the given verified phone number entry.
    
    verified_number The VerifiedNumber entry to use when sending.
    text            The text of the message to send.
    
    return  True on success, False on failure
    """
    backend = verified_number.backend
    msg = SMSLog(
        couch_recipient_doc_type = verified_number.owner_doc_type,
        couch_recipient = verified_number.owner_id,
        phone_number = "+" + str(verified_number.phone_number),
        direction = OUTGOING,
        date = datetime.utcnow(),
        domain = verified_number.domain,
        backend_id = backend._id,
        text = text
    )
    add_msg_tags(msg, **kwargs)

    def onerror():
        logging.exception("Exception while sending SMS to VerifiedNumber id " + verified_number._id)
    return queue_outgoing_sms(msg, onerror=onerror)

def send_sms_with_backend(domain, phone_number, text, backend_id, **kwargs):
    phone_number = clean_phone_number(phone_number)
    msg = SMSLog(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=datetime.utcnow(),
        backend_id=backend_id,
        text=text
    )
    add_msg_tags(msg, **kwargs)

    def onerror():
        logging.exception("Exception while sending SMS to %s with backend %s" % (phone_number, backend_id))
    return queue_outgoing_sms(msg, onerror=onerror)

def send_sms_with_backend_name(domain, phone_number, text, backend_name, **kwargs):
    phone_number = clean_phone_number(phone_number)
    backend = MobileBackend.load_by_name(domain, backend_name)
    msg = SMSLog(
        domain=domain,
        phone_number=phone_number,
        direction=OUTGOING,
        date=datetime.utcnow(),
        backend_id=backend._id,
        text=text
    )
    add_msg_tags(msg, **kwargs)

    def onerror():
        logging.exception("Exception while sending SMS to %s with backend name %s from domain %s" % (phone_number, backend_name, domain))
    return queue_outgoing_sms(msg, onerror=onerror)

def enqueue_directly(msg):
    try:
        from corehq.apps.sms.management.commands.run_sms_queue import SMSEnqueuingOperation
        SMSEnqueuingOperation().enqueue_directly(msg)
    except:
        # If this direct enqueue fails, no problem, it will get picked up
        # shortly.
        pass

def queue_outgoing_sms(msg, onerror=lambda: None):
    if settings.SMS_QUEUE_ENABLED:
        try:
            msg.processed = False
            msg.datetime_to_process = msg.date
            msg.save()
        except:
            onerror()
            return False

        enqueue_directly(msg)
        return True
    else:
        msg.processed = True
        return send_message_via_backend(msg, onerror=onerror)


@task
def store_billable(msg):
    SmsBillable.create(msg)


def send_message_via_backend(msg, backend=None, onerror=lambda: None):
    """send sms using a specific backend

    msg - outbound message object
    backend - MobileBackend object to use for sending; if None, use
      msg.outbound_backend
    onerror - error handler; mostly useful for logging a custom message to the
      error log
    """
    try:
        msg.text = clean_text(msg.text)
    except Exception:
        logging.exception("Could not clean text for sms dated '%s' in domain '%s'" % (msg.date, msg.domain))
    try:
        if not backend:
            backend = msg.outbound_backend
            # note: this will handle "verified" contacts that are still pending
            # verification, thus the backend is None. it's best to only call
            # send_sms_to_verified_number on truly verified contacts, though

        if not msg.backend_id:
            msg.backend_id = backend._id

        if backend.domain_is_authorized(msg.domain):
            backend.send(msg)
        else:
            raise BackendAuthorizationException("Domain '%s' is not authorized to use backend '%s'" % (msg.domain, backend._id))

        try:
            msg.backend_api = backend.__class__.get_api_id()
        except Exception:
            pass
        msg.save()
        store_billable.delay(msg)
        return True
    except Exception:
        onerror()
        return False

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

def incoming(phone_number, text, backend_api, timestamp=None, domain_scope=None, backend_message_id=None, delay=True):
    """
    entry point for incoming sms

    phone_number - originating phone number
    text - message content
    backend_api - backend API ID of receiving sms backend
    timestamp - message received timestamp; defaults to now (UTC)
    domain_scope - if present, only messages from phone numbers that can be
      definitively linked to this domain will be processed; others will be
      dropped (useful to provide security when simulating incoming sms)
    """
    # Log message in message log
    phone_number = clean_phone_number(phone_number)
    msg = SMSLog(
        phone_number = phone_number,
        direction = INCOMING,
        date = timestamp or datetime.utcnow(),
        text = text,
        domain_scope = domain_scope,
        backend_api = backend_api,
        backend_message_id = backend_message_id,
    )
    if settings.SMS_QUEUE_ENABLED:
        msg.processed = False
        msg.datetime_to_process = datetime.utcnow()
        msg.save()
        enqueue_directly(msg)
    else:
        msg.processed = True
        msg.save()
        process_incoming(msg, delay=delay)
    return msg

def process_incoming(msg, delay=True):
    v = VerifiedNumber.by_phone(msg.phone_number, include_pending=True)

    if v is not None and v.verified:
        msg.couch_recipient_doc_type = v.owner_doc_type
        msg.couch_recipient = v.owner_id
        msg.domain = v.domain
        msg.save()

    if msg.domain_scope:
        # only process messages for phones known to be associated with this domain
        if v is None or v.domain != msg.domain_scope:
            raise DomainScopeValidationError(
                'Attempted to simulate incoming sms from phone number not ' \
                'verified with this domain'
            )
    store_billable.delay(msg)
    create_billable_for_sms(msg, msg.backend_api, delay=delay)

    if v is not None and v.verified:
        for h in settings.SMS_HANDLERS:
            try:
                handler = to_function(h)
            except:
                logging.exception('error loading sms handler: %s' % h)
                continue

            try:
                was_handled = handler(v, msg.text, msg=msg)
            except Exception, e:
                logging.exception('unhandled error in sms handler %s for message [%s]: %s' % (h, msg._id, e))
                was_handled = False

            if was_handled:
                break
    else:
        if not process_sms_registration(msg):
            import verify
            verify.process_verification(msg.phone_number, msg)

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

class StructuredSMSException(Exception):
    response_text = ""

def handle_structured_sms(survey_keyword, survey_keyword_action, contact, verified_number, text, send_response=False, msg=None):
    domain = contact.domain
    contact_doc_type = contact.doc_type
    contact_id = contact._id

    text = text.strip()
    if survey_keyword.delimiter is not None:
        args = text.split(survey_keyword.delimiter)
    else:
        args = text.split()

    keyword = args[0].strip().upper()

    error_occurred = False
    error_msg = None
    session = None

    try:
        # Start the session
        form = Form.get_form(survey_keyword_action.form_unique_id)
        app = form.get_app()
        module = form.get_module()

        if contact_doc_type == "CommCareCase":
            case_id = contact_id
        else:
            #TODO: Need a way to choose the case when it's a user that's playing the form
            case_id = None

        session, responses = start_session(domain, contact, app, module, form, case_id=case_id, yield_responses=True)
        session.workflow = WORKFLOW_KEYWORD
        session.save()
        if msg is not None:
            msg.workflow = WORKFLOW_KEYWORD
            msg.xforms_session_couch_id = session._id
            msg.save()
        assert len(responses) > 0, "There should be at least one response."

        current_question = responses[-1]
        form_complete = is_form_complete(current_question)

        if not form_complete:
            if survey_keyword_action.use_named_args:
                # Arguments in the sms are named
                xpath_answer = {} # Dictionary of {xpath : answer}
                for answer in args[1:]:
                    answer = answer.strip()
                    answer_upper = answer.upper()
                    if survey_keyword_action.named_args_separator is not None:
                        # A separator is used for naming arguments; for example, the "=" in "register name=joe age=25"
                        answer_parts = answer.partition(survey_keyword_action.named_args_separator)
                        if answer_parts[1] != survey_keyword_action.named_args_separator:
                            raise StructuredSMSException(response_text="ERROR: Expected name and value to be joined by '%(separator)s'" % {"separator" : survey_keyword_action.named_args_separator})
                        else:
                            arg_name = answer_parts[0].upper().strip()
                            xpath = survey_keyword_action.named_args.get(arg_name, None)
                            if xpath is not None:
                                if xpath in xpath_answer:
                                    raise StructuredSMSException(response_text="ERROR: More than one answer found for '%(arg_name)s'" % {"arg_name" : arg_name})

                                xpath_answer[xpath] = answer_parts[2].strip()
                            else:
                                # Ignore unexpected named arguments
                                pass
                    else:
                        # No separator is used for naming arguments; for example, "update a100 b34 c5"
                        matches = 0
                        for k, v in survey_keyword_action.named_args.items():
                            if answer_upper.startswith(k):
                                matches += 1
                                if matches > 1:
                                    raise StructuredSMSException(response_text="ERROR: More than one question matches '%(answer)s'" % {"answer" : answer})

                                if v in xpath_answer:
                                    raise StructuredSMSException(response_text="ERROR: More than one answer found for '%(named_arg)s'" % {"named_arg" : k})

                                xpath_answer[v] = answer[len(k):].strip()

                        if matches == 0:
                            # Ignore unexpected named arguments
                            pass

                # Go through each question in the form, answering only the questions that the sms has answers for
                while not form_complete:
                    if current_question.is_error:
                        raise StructuredSMSException(response_text=(current_question.text_prompt or "ERROR: Internal server error"))

                    xpath = current_question.event._dict["binding"]
                    if xpath in xpath_answer:
                        valid, answer, _error_msg = validate_answer(current_question.event, xpath_answer[xpath])
                        if not valid:
                            raise StructuredSMSException(response_text=_error_msg)
                        responses = _get_responses(domain, contact_id, answer, yield_responses=True, session_id=session.session_id, update_timestamp=False)
                    else:
                        responses = _get_responses(domain, contact_id, "", yield_responses=True, session_id=session.session_id, update_timestamp=False)

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
                        raise StructuredSMSException(response_text=(current_question.text_prompt or "ERROR: Internal server error"))

                    valid, answer, _error_msg = validate_answer(current_question.event, answer.strip())
                    if not valid:
                        raise StructuredSMSException(response_text=_error_msg)

                    responses = _get_responses(domain, contact_id, answer, yield_responses=True, session_id=session.session_id, update_timestamp=False)
                    current_question = responses[-1]
                    form_complete = is_form_complete(current_question)

                # If the form isn't finished yet but we're out of arguments, try to leave each remaining question blank and continue
                while not form_complete:
                    responses = _get_responses(domain, contact_id, "", yield_responses=True, session_id=session.session_id, update_timestamp=False)
                    current_question = responses[-1]

                    if current_question.is_error:
                        raise StructuredSMSException(response_text=(current_question.text_prompt or "ERROR: Internal server error"))

                    if is_form_complete(current_question):
                        form_complete = True
    except StructuredSMSException as sse:
        error_occurred = True
        error_msg = sse.response_text
    except Exception:
        logging.exception("Could not process structured sms for contact %s, domain %s, keyword %s" % (contact_id, domain, keyword))
        error_occurred = True
        error_msg = "ERROR: Internal server error"

    if session is not None:
        session = XFormsSession.get(session._id)
        if session.is_open:
            session.end(False)
            session.save()

    message_tags = {
        "workflow" : WORKFLOW_KEYWORD,
        "xforms_session_couch_id": session._id if session is not None else None,
    }

    if msg is not None:
        msg.workflow = message_tags["workflow"]
        msg.xforms_session_couch_id = message_tags["xforms_session_couch_id"]
        msg.save()

    if error_occurred and verified_number is not None and send_response:
        send_sms_to_verified_number(verified_number, error_msg, **message_tags)

def process_survey_keyword_actions(verified_number, survey_keyword, text, msg=None):
    from corehq.apps.reminders.models import (
        RECIPIENT_SENDER,
        RECIPIENT_OWNER,
        RECIPIENT_USER_GROUP,
        METHOD_SMS,
        METHOD_SMS_SURVEY,
        METHOD_STRUCTURED_SMS,
        REMINDER_TYPE_KEYWORD_INITIATED,
    )
    sender = verified_number.owner
    if sender.doc_type == "CommCareCase":
        case = sender
    else:
        case = None
    for survey_keyword_action in survey_keyword.actions:
        if survey_keyword_action.recipient == RECIPIENT_SENDER:
            contact = sender
        elif survey_keyword_action.recipient == RECIPIENT_OWNER:
            if sender.doc_type == "CommCareCase":
                contact = get_wrapped_owner(get_owner_id(sender))
            else:
                contact = None
        elif survey_keyword_action.recipient == RECIPIENT_USER_GROUP:
            try:
                contact = Group.get(survey_keyword_action.recipient_id)
                assert contact.doc_type == "Group"
                assert contact.domain == verified_number.domain
            except Exception:
                contact = None
        else:
            contact = None

        if contact is None:
            continue

        if survey_keyword_action.action == METHOD_SMS:
            create_immediate_reminder(contact, METHOD_SMS, reminder_type=REMINDER_TYPE_KEYWORD_INITIATED, message=survey_keyword_action.message_content, case=case)
        elif survey_keyword_action.action == METHOD_SMS_SURVEY:
            create_immediate_reminder(contact, METHOD_SMS_SURVEY, reminder_type=REMINDER_TYPE_KEYWORD_INITIATED, form_unique_id=survey_keyword_action.form_unique_id, case=case)
        elif survey_keyword_action.action == METHOD_STRUCTURED_SMS:
            handle_structured_sms(survey_keyword, survey_keyword_action, sender, verified_number, text, send_response=True, msg=msg)

def sms_keyword_handler(v, text, msg=None):
    from corehq.apps.reminders.models import SurveyKeyword

    text = text.strip()
    if text == "":
        return False

    sessions = XFormsSession.get_all_open_sms_sessions(v.domain, v.owner_id)
    any_session_open = len(sessions) > 0
    text_words = text.upper().split()

    if text.startswith("#"):
        if len(text_words) > 0 and text_words[0] == "#START":
            # Respond to "#START <keyword>" command
            if len(text_words) > 1:
                sk = SurveyKeyword.get_keyword(v.domain, text_words[1])
                if sk is not None:
                    if len(sk.initiator_doc_type_filter) > 0 and v.owner_doc_type not in sk.initiator_doc_type_filter:
                        # The contact type is not allowed to invoke this keyword
                        return False
                    process_survey_keyword_actions(v, sk, text[6:].strip(), msg=msg)
                else:
                    send_sms_to_verified_number(v, "Keyword not found: '%s'." % text_words[1], workflow=WORKFLOW_KEYWORD)
            else:
                send_sms_to_verified_number(v, "Usage: #START <keyword>", workflow=WORKFLOW_KEYWORD)
        elif len(text_words) > 0 and text_words[0] == "#STOP":
            # Respond to "#STOP" keyword
            XFormsSession.close_all_open_sms_sessions(v.domain, v.owner_id)
        elif len(text_words) > 0 and text_words[0] == "#CURRENT":
            # Respond to "#CURRENT" keyword
            if len(sessions) == 1:
                resp = current_question(sessions[0].session_id)
                send_sms_to_verified_number(v, resp.event.text_prompt, workflow=sessions[0].workflow, reminder_id=sessions[0].reminder_id, xforms_session_couch_id=sessions[0]._id)
        else:
            # Response to unknown command
            send_sms_to_verified_number(v, "Unknown command: '%s'" % text_words[0])
        if msg is not None:
            msg.workflow = WORKFLOW_KEYWORD
            msg.save()
        return True
    else:
        for survey_keyword in SurveyKeyword.get_all(v.domain):
            if survey_keyword.delimiter is not None:
                args = text.split(survey_keyword.delimiter)
            else:
                args = text.split()

            keyword = args[0].strip().upper()
            if keyword == survey_keyword.keyword.upper():
                if any_session_open and not survey_keyword.override_open_sessions:
                    # We don't want to override any open sessions, so just pass and let the form session handler handle the message
                    return False
                elif len(survey_keyword.initiator_doc_type_filter) > 0 and v.owner_doc_type not in survey_keyword.initiator_doc_type_filter:
                    # The contact type is not allowed to invoke this keyword
                    return False
                else:
                    process_survey_keyword_actions(v, survey_keyword, text, msg=msg)
                    if msg is not None:
                        msg.workflow = WORKFLOW_KEYWORD
                        msg.save()
                    return True
        # No keywords matched, so pass the message onto the next handler
        return False

def form_session_handler(v, text, msg=None):
    """
    The form session handler will use the inbound text to answer the next question
    in the open XformsSession for the associated contact. If no session is open,
    the handler passes. If multiple sessions are open, they are all closed and an
    error message is displayed to the user.
    """
    sessions = XFormsSession.get_all_open_sms_sessions(v.domain, v.owner_id)
    if len(sessions) > 1:
        # If there are multiple sessions, there's no way for us to know which one this message
        # belongs to. So we should inform the user that there was an error and to try to restart
        # the survey.
        for session in sessions:
            session.end(False)
            session.save()
        send_sms_to_verified_number(v, "An error has occurred. Please try restarting the survey.")
        return True

    session = sessions[0] if len(sessions) == 1 else None

    if session is not None:
        if msg is not None:
            msg.workflow = session.workflow
            msg.reminder_id = session.reminder_id
            msg.xforms_session_couch_id = session._id
            msg.save()

        # If there's an open session, treat the inbound text as the answer to the next question
        try:
            resp = current_question(session.session_id)
            event = resp.event
            valid, text, error_msg = validate_answer(event, text)
            
            if valid:
                responses = _get_responses(v.domain, v.owner_id, text)
                if len(responses) > 0:
                    response_text = format_message_list(responses)
                    send_sms_to_verified_number(v, response_text, workflow=session.workflow, reminder_id=session.reminder_id, xforms_session_couch_id=session._id)
            else:
                send_sms_to_verified_number(v, error_msg + event.text_prompt, workflow=session.workflow, reminder_id=session.reminder_id, xforms_session_couch_id=session._id)
        except Exception:
            # Catch any touchforms errors
            msg_id = msg._id if msg is not None else ""
            logging.exception("Exception in form_session_handler for message id %s." % msg_id)
            send_sms_to_verified_number(v, "An error has occurred. Please try again later. If the problem persists, try restarting the survey.")
        return True
    else:
        return False

def forwarding_handler(v, text, msg=None):
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

def fallback_handler(v, text, msg=None):
    domain_obj = Domain.get_by_name(v.domain, strict=True)
    if domain_obj.use_default_sms_response and domain_obj.default_sms_response:
        send_sms_to_verified_number(v, domain_obj.default_sms_response)
    return True


