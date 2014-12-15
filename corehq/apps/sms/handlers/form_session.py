from corehq.apps.sms.api import (
    MessageMetadata,
    add_msg_tags,
    send_sms_to_verified_number,
    log_sms_exception,
)
from corehq.apps.sms.messages import *
from corehq.apps.sms.util import format_message_list
from touchforms.formplayer.api import current_question
from corehq.apps.smsforms.app import (
    _get_responses,
    _responses_to_text,
    start_session,
)
from dateutil.parser import parse
from corehq.apps.smsforms.models import XFormsSession
import logging

def form_session_handler(v, text, msg):
    """
    The form session handler will use the inbound text to answer the next question
    in the open XformsSession for the associated contact. If no session is open,
    the handler passes. If multiple sessions are open, they are all closed and an
    error message is displayed to the user.
    """
    multiple, session = get_single_open_session(v.domain, v.owner_id)
    if multiple:
        send_sms_to_verified_number(v, get_message(MSG_MULTIPLE_SESSIONS, v))
        return True

    if session:
        # Metadata to be applied to the inbound message
        inbound_metadata = MessageMetadata(
            workflow=session.workflow,
            reminder_id=session.reminder_id,
            xforms_session_couch_id=session._id,
        )
        add_msg_tags(msg, inbound_metadata)

        try:
            answer_next_question(v, text, msg, session)
        except Exception:
            # Catch any touchforms errors
            log_sms_exception(msg)
            send_sms_to_verified_number(v, get_message(MSG_TOUCHFORMS_DOWN, v))
        return True
    else:
        return False

def get_single_open_session(domain, contact_id):
    """
      Retrieves the current open XFormsSession for the given contact.
      If multiple sessions are open, it closes all of them and returns
    None for the session.
      The return value is a tuple of (multiple, session), where multiple
    is True if there were multiple sessions, and session is the session if
    there was a single open session available.
    """
    sessions = XFormsSession.get_all_open_sms_sessions(domain, contact_id)
    if len(sessions) > 1:
        for session in sessions:
            session.end(False)
            session.save()
        return (True, None)

    session = sessions[0] if len(sessions) == 1 else None
    return (False, session)

def answer_next_question(v, text, msg, session):
    resp = current_question(session.session_id)
    event = resp.event
    valid, text, error_msg = validate_answer(event, text, v)

    # metadata to be applied to the reply message
    outbound_metadata = MessageMetadata(
        workflow=session.workflow,
        reminder_id=session.reminder_id,
        xforms_session_couch_id=session._id,
    )

    if valid:
        responses = _get_responses(v.domain, v.owner_id, text,
            yield_responses=True)

        if has_invalid_response(responses):
            mark_as_invalid_response(msg)

        text_responses = _responses_to_text(responses)
        if len(text_responses) > 0:
            response_text = format_message_list(text_responses)
            send_sms_to_verified_number(v, response_text, 
                metadata=outbound_metadata)
    else:
        mark_as_invalid_response(msg)
        response_text = "%s %s" % (error_msg, event.text_prompt)
        send_sms_to_verified_number(v, response_text, 
            metadata=outbound_metadata)

def validate_answer(event, text, v):
    text = text.strip()
    upper_text = text.upper()
    valid = False
    error_msg = ""
    if text == "" and event._dict.get("required", False):
        return (False, text, get_message(MSG_FIELD_REQUIRED, v))

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
                    error_msg = get_message(MSG_CHOICE_OUT_OF_RANGE, v)
            except ValueError:
                error_msg = get_message(MSG_INVALID_CHOICE, v)

    # Validate multiselect
    elif event.datatype == "multiselect":
        choices = format_choices(event._dict["choices"])
        max_index = len(event._dict["choices"])
        proposed_answers = text.split()
        final_answers = {}

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
            error_msg = get_message(MSG_INVALID_CHOICE, v)

    # Validate int
    elif event.datatype == "int":
        try:
            int(text)
            valid = True
        except ValueError:
            error_msg = get_message(MSG_INVALID_INT, v)
    
    # Validate float
    elif event.datatype == "float":
        try:
            float(text)
            valid = True
        except ValueError:
            error_msg = get_message(MSG_INVALID_FLOAT, v)
    
    # Validate longint
    elif event.datatype == "longint":
        try:
            long(text)
            valid = True
        except ValueError:
            error_msg = get_message(MSG_INVALID_LONG, v)
    
    # Validate date (Format: YYYYMMDD)
    elif event.datatype == "date":
        try:
            assert len(text) == 8
            int(text)
            text = "%s-%s-%s" % (text[0:4], text[4:6], text[6:])
            parse(text)
            valid = True
        except Exception:
            error_msg = get_message(MSG_INVALID_DATE, v)

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
            error_msg = get_message(MSG_INVALID_TIME, v)

    # Other question types pass
    else:
        valid = True

    return (valid, text, error_msg)

def format_choices(choices_list):
    choices = {}
    for idx, choice in enumerate(choices_list):
        choices[choice.strip().upper()] = idx + 1
    return choices

def has_invalid_response(responses):
    for r in responses:
        if r.status == "validation-error":
            return True
    return False

def mark_as_invalid_response(msg):
    msg.invalid_survey_response = True
    msg.save()

