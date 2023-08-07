from datetime import datetime

from dimagi.utils.logging import notify_error

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.formplayer_api.smsforms.api import FormplayerInterface
from corehq.apps.sms.api import (
    MessageMetadata,
    add_msg_tags,
    log_sms_exception,
    send_sms_to_verified_number,
)
from corehq.apps.sms.messages import (
    MSG_CHOICE_OUT_OF_RANGE,
    MSG_FIELD_REQUIRED,
    MSG_INVALID_CHOICE,
    MSG_INVALID_DATE,
    MSG_INVALID_FLOAT,
    MSG_INVALID_INT,
    MSG_INVALID_INT_RANGE,
    MSG_INVALID_LONG,
    MSG_INVALID_TIME,
    MSG_GENERIC_ERROR,
    MSG_TOUCHFORMS_DOWN,
    get_message,
)
from corehq.apps.sms.util import format_message_list, get_date_format
from corehq.apps.smsforms.app import (
    _responses_to_text,
    get_events_from_responses,
    get_responses,
)
from corehq.apps.smsforms.models import (
    SQLXFormsSession,
    XFormsSessionSynchronization,
    get_channel_for_contact,
)
from corehq.apps.smsforms.util import critical_section_for_smsforms_sessions


def form_session_handler(verified_number, text, msg):
    """
    The form session handler will use the inbound text to answer the next question
    in the open SQLXformsSession for the associated contact. If no session is open,
    the handler passes. If multiple sessions are open, they are all closed and an
    error message is displayed to the user.
    """
    with critical_section_for_smsforms_sessions(verified_number.owner_id):
        if toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(verified_number.domain):
            channel = get_channel_for_contact(verified_number.owner_id, verified_number.phone_number)
            running_session_info = XFormsSessionSynchronization.get_running_session_info_for_channel(channel)
            if running_session_info.session_id:
                session = SQLXFormsSession.by_session_id(running_session_info.session_id)
                if session.connection_id != verified_number.owner_id:
                    notify_error("SMS response contact does not match open session contact", details={
                        "session_id": session.session_id,
                        "phone_number_id": verified_number.couch_id,
                        "message_id": msg.couch_id
                    })
                    session.mark_completed(False)  # this will also release the channel
                    send_sms_to_verified_number(
                        verified_number, get_message(MSG_GENERIC_ERROR, verified_number)
                    )
                    return True
                if not session.session_is_open:
                    # This should never happen. But if it does we should set the channel free
                    # and act like there was no available session
                    notify_error("The supposedly running session was not open and was released. "
                                 'No known way for this to happen, so worth investigating.')
                    XFormsSessionSynchronization.clear_stale_channel_claim(channel)
                    session = None
            else:
                session = None
        else:
            multiple, session = get_single_open_session_or_close_multiple(
                verified_number.domain, verified_number.owner_id
            )
            if multiple:
                send_sms_to_verified_number(verified_number, get_message(MSG_GENERIC_ERROR, verified_number))
                return True

        if session:
            session.phone_number = verified_number.phone_number
            session.modified_time = datetime.utcnow()
            session.save()

            subevent = session.related_subevent
            subevent_id = subevent.id if subevent else None

            # Metadata to be applied to the inbound message
            inbound_metadata = MessageMetadata(
                workflow=session.workflow,
                reminder_id=session.reminder_id,
                xforms_session_couch_id=session._id,
                messaging_subevent_id=subevent_id,
            )
            add_msg_tags(msg, inbound_metadata)
            msg.save()
            try:
                answer_next_question(verified_number, text, msg, session, subevent_id)
            except Exception:
                # Catch any touchforms errors
                log_sms_exception(msg)
                send_sms_to_verified_number(verified_number, get_message(MSG_TOUCHFORMS_DOWN, verified_number))
            return True
        else:
            return False


def get_single_open_session_or_close_multiple(domain, contact_id):
    """
    Retrieves the current open SQLXFormsSession for the given contact.
    If multiple sessions are open, it closes all of them and returns
    None for the session.

    The return value is a tuple of (multiple, session), where multiple
    is True if there were multiple sessions, and session is the session if
    there was a single open session available.
    """
    sessions = SQLXFormsSession.get_all_open_sms_sessions(domain, contact_id)
    count = sessions.count()
    if count > 1:
        for session in sessions:
            session.mark_completed(False)
        return (True, None)

    session = sessions[0] if count == 1 else None
    return (False, session)


def answer_next_question(verified_number, text, msg, session, subevent_id):
    resp = FormplayerInterface(session.session_id, verified_number.domain).current_question()
    event = resp.event
    valid, text, error_msg = validate_answer(event, text, verified_number)

    # metadata to be applied to the reply message
    outbound_metadata = MessageMetadata(
        workflow=session.workflow,
        reminder_id=session.reminder_id,
        xforms_session_couch_id=session._id,
        messaging_subevent_id=subevent_id,
    )

    if valid:
        responses = get_responses(verified_number.domain, session.session_id, text)

        if has_invalid_response(responses):
            mark_as_invalid_response(msg)

        text_responses = _responses_to_text(responses)
        events = get_events_from_responses(responses)
        if len(text_responses) > 0:
            response_text = format_message_list(text_responses)
            send_sms_to_verified_number(verified_number, response_text,
                                        metadata=outbound_metadata, events=events)
    else:
        mark_as_invalid_response(msg)
        response_text = "%s %s" % (error_msg, event.text_prompt)
        send_sms_to_verified_number(verified_number, response_text,
                                    metadata=outbound_metadata, events=[event])


def validate_answer(event, text, verified_number):
    text = text.strip()
    upper_text = text.upper()
    valid = False
    error_msg = ""
    if text == "" and event._dict.get("required", False):
        return (False, text, get_message(MSG_FIELD_REQUIRED, verified_number))

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
                    error_msg = get_message(MSG_CHOICE_OUT_OF_RANGE, verified_number)
            except ValueError:
                error_msg = get_message(MSG_INVALID_CHOICE, verified_number)

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
            text = " ".join(final_answers)
            valid = True
        except Exception:
            error_msg = get_message(MSG_INVALID_CHOICE, verified_number)

    # Validate int
    elif event.datatype == "int":
        try:
            value = int(text)
            if value >= -2147483648 and value <= 2147483647:
                valid = True
            else:
                error_msg = get_message(MSG_INVALID_INT_RANGE, verified_number)
        except ValueError:
            error_msg = get_message(MSG_INVALID_INT, verified_number)
    
    # Validate float
    elif event.datatype == "float":
        try:
            float(text)
            valid = True
        except ValueError:
            error_msg = get_message(MSG_INVALID_FLOAT, verified_number)
    
    # Validate longint
    elif event.datatype == "longint":
        try:
            int(text)
            valid = True
        except ValueError:
            error_msg = get_message(MSG_INVALID_LONG, verified_number)
    
    # Validate date (Format: specified by Domain.sms_survey_date_format, default: YYYYMMDD)
    elif event.datatype == "date":
        domain_obj = Domain.get_by_name(verified_number.domain)
        df = get_date_format(domain_obj.sms_survey_date_format)

        if df.is_valid(text):
            try:
                text = df.parse(text).strftime('%Y-%m-%d')
                valid = True
            except (ValueError, TypeError):
                pass

        if not valid:
            error_msg = get_message(MSG_INVALID_DATE, verified_number, context=(df.human_readable_format,))

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
            error_msg = get_message(MSG_INVALID_TIME, verified_number)

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
