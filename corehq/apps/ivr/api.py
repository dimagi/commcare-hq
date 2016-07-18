from datetime import datetime
from corehq.apps.ivr.models import Call
from corehq.apps.sms.models import (INCOMING, OUTGOING,
    MessagingSubEvent, MessagingEvent, SQLMobileBackend,
    PhoneNumber)
from corehq.apps.sms.util import strip_plus
from corehq.apps.smsforms.app import start_session, _get_responses
from corehq.apps.smsforms.models import XFORMS_SESSION_IVR, get_session_by_session_id
from corehq.apps.app_manager.models import Form
from django.http import HttpResponse
from django.conf import settings
from dimagi.utils.web import get_url_base
from touchforms.formplayer.api import current_question, TouchformsError
from corehq.apps.smsforms.app import submit_unfinished_form
from corehq.apps.smsforms.util import form_requires_input


IVR_EVENT_NEW_CALL = "NEW_CALL"
IVR_EVENT_INPUT = "INPUT"
IVR_EVENT_DISCONNECT = "DISCONNECT"


class GatewayConnectionError(Exception):
    pass


class IVRResponseData(object):

    def __init__(self, ivr_responses, input_length, session):
        self.ivr_responses = ivr_responses
        self.input_length = input_length
        self.session = session


def convert_media_path_to_hq_url(path, app):
    media = app.multimedia_map.get(path, None)
    if media is None:
        return None
    else:
        url_base = get_url_base()
        return url_base + media.url + "foo.wav"


def validate_answer(answer, question):
    """
    Return True if answer is a valid response to question, False if not.
    (question is expected to be the XFormsResponse object for the question)
    """
    if question.event.datatype == "select":
        try:
            assert answer is not None
            answer = int(answer)
            assert answer >= 1 and answer <= len(question.event.choices)
            return True
        except (ValueError, AssertionError):
            return False
    else:
        try:
            assert answer is not None
            if isinstance(answer, basestring):
                assert len(answer.strip()) > 0
            return True
        except AssertionError:
            return False


def format_ivr_response(text, app):
    return {
        "text_to_say" : text,
        "audio_file_url" : convert_media_path_to_hq_url(text, app) if text.startswith("jr://") else None,
    }


def get_input_length(question):
    if question.event.type == "question" and question.event.datatype == "select":
        return 1
    else:
        return None


def hang_up_response(gateway_session_id, backend=None):
    if backend:
        return HttpResponse(backend.get_response(
            gateway_session_id,
            [],
            collect_input=False,
            hang_up=True
        ))
    else:
        return HttpResponse("")


def add_metadata(call_log_entry, duration=None):
    try:
        call_log_entry.duration = int(round(float(duration)))
        call_log_entry.save()
    except (TypeError, ValueError):
        pass


def get_app_module_form(call_log_entry, logged_subevent):
    """
    Returns (app, module, form, error)
    """
    try:
        form = Form.get_form(call_log_entry.form_unique_id)
        app = form.get_app()
        module = form.get_module()
        return (app, module, form, False)
    except:
        log_error(MessagingEvent.ERROR_CANNOT_FIND_FORM,
            call_log_entry, logged_subevent)
        return (None, None, None, True)


def start_call_session(recipient, call_log_entry, logged_subevent, app, module, form):
    """
    Returns (session, responses, error)
    """
    try:
        session, responses = start_session(recipient.domain, recipient, app,
            module, form, call_log_entry.case_id, yield_responses=True,
            session_type=XFORMS_SESSION_IVR,
            case_for_case_submission=call_log_entry.case_for_case_submission)

        if logged_subevent:
            logged_subevent.xforms_session = session
            logged_subevent.save()

        if len(responses) == 0:
            log_error(MessagingEvent.ERROR_FORM_HAS_NO_QUESTIONS,
                call_log_entry, logged_subevent)
            return (session, responses, True)

        return (session, responses, False)
    except TouchformsError as e:
        additional_error_text = e.response_data.get('human_readable_message', None)
        log_error(MessagingEvent.ERROR_TOUCHFORMS_ERROR,
            call_log_entry, logged_subevent, additional_error_text=additional_error_text)
        return (None, None, True)


def get_ivr_responses_from_touchforms_responses(call_log_entry, responses, app):
    """
    responses is a list of XFormsResponse objects
    app is the app from which the form came
    """
    ivr_responses = []
    question_constraint_failed = False
    hang_up = False
    for response in responses:
        if response.status == 'validation-error':
            question_constraint_failed = True
            call_log_entry.current_question_retry_count += 1
            ivr_responses.append(format_ivr_response(response.text_prompt, app))
        elif response.status == 'http-error':
            ivr_responses = []
            hang_up = True
            break
        elif response.event.type == "question":
            ivr_responses.append(format_ivr_response(response.event.caption, app))
        elif response.event.type == "form-complete":
            hang_up = True
    return (ivr_responses, question_constraint_failed, hang_up)


def process_disconnect(call_log_entry):
    if call_log_entry.xforms_session_id is not None:
        session = get_session_by_session_id(call_log_entry.xforms_session_id)
        if session.is_open:
            if call_log_entry.submit_partial_form:
                submit_unfinished_form(session.session_id,
                    call_log_entry.include_case_side_effects)
            else:
                session.end(completed=False)
                session.save()


def answer_question(call_log_entry, recipient, input_data, logged_subevent=None):
    """
    Returns a list of (responses, answer_is_valid), where responses is the
    list of XFormsResponse objects from touchforms and answer_is_valid is
    True if input_data passes validation and False if not.

    Returning an empty list for responses will end up forcing a hangup
    later on in the workflow.
    """
    if call_log_entry.xforms_session_id is None:
        return ([], None)

    try:
        current_q = current_question(call_log_entry.xforms_session_id)
    except TouchformsError as e:
        log_touchforms_error(e, call_log_entry, logged_subevent)
        return ([], None)

    if current_q.status == 'http-error':
        log_error(MessagingEvent.ERROR_TOUCHFORMS_ERROR, call_log_entry,
            logged_subevent)
        return ([], None)

    if validate_answer(input_data, current_q):
        answer_is_valid = True
        try:
            responses = _get_responses(recipient.domain, recipient.get_id,
                input_data, yield_responses=True,
                session_id=call_log_entry.xforms_session_id)
        except TouchformsError as e:
            log_touchforms_error(e, call_log_entry, logged_subevent)
            return ([], None)
    else:
        answer_is_valid = False
        call_log_entry.current_question_retry_count += 1
        responses = [current_q]

    return (responses, answer_is_valid)


def handle_known_call_session(call_log_entry, backend, ivr_event,
        input_data=None, logged_subevent=None):
    if (ivr_event == IVR_EVENT_NEW_CALL and
            call_log_entry.use_precached_first_response):
        # This means we precached the first IVR response when we
        # initiated the call, so all we need to do is return that
        # response.
        return HttpResponse(call_log_entry.first_response)

    app, module, form, error = get_app_module_form(call_log_entry, logged_subevent)
    if error:
        return hang_up_response(call_log_entry.gateway_session_id,
            backend=backend)

    recipient = call_log_entry.recipient

    answer_is_valid = True
    if ivr_event == IVR_EVENT_NEW_CALL:
        session, responses, error = start_call_session(recipient,
            call_log_entry, logged_subevent, app, module, form)
        if error:
            return hang_up_response(call_log_entry.gateway_session_id,
                backend=backend)
        call_log_entry.xforms_session_id = session.session_id
    elif ivr_event == IVR_EVENT_INPUT:
        responses, answer_is_valid = answer_question(call_log_entry, recipient,
            input_data, logged_subevent=logged_subevent)
    else:
        responses = []

    ivr_responses, question_constraint_failed, hang_up = \
        get_ivr_responses_from_touchforms_responses(call_log_entry, responses, app)

    if answer_is_valid and not question_constraint_failed:
        # If there were no validation errors (including question contraint errors),
        # then reset the current question retry count to 0.
        call_log_entry.current_question_retry_count = 0

    if (call_log_entry.max_question_retries is not None and
            call_log_entry.current_question_retry_count > call_log_entry.max_question_retries):
        # We have retried to current question too many times without
        # getting a valid answer, so force a hang-up.
        ivr_responses = []

    if len(ivr_responses) == 0:
        hang_up = True

    input_length = None
    if hang_up:
        process_disconnect(call_log_entry)
    else:
        # Set input_length to let the ivr gateway know how many digits we need to collect.
        # If the latest XFormsResponse we have was a response to a contraint error, then
        # it won't have an event, so in that case we have to get the current question again.
        if question_constraint_failed:
            current_q = current_question(call_log_entry.xforms_session_id)
        else:
            current_q = responses[-1]

        input_length = get_input_length(current_q)

    call_log_entry.save()

    return HttpResponse(
        backend.get_response(call_log_entry.gateway_session_id,
            ivr_responses, collect_input=(not hang_up), hang_up=hang_up,
            input_length=input_length))


def log_call(phone_number, gateway_session_id, backend=None):
    cleaned_number = strip_plus(phone_number)
    v = PhoneNumber.by_extensive_search(cleaned_number)

    call = Call(
        phone_number=cleaned_number,
        direction=INCOMING,
        date=datetime.utcnow(),
        backend_api=backend.get_api_id() if backend else None,
        backend_id=backend.couch_id if backend else None,
        gateway_session_id=gateway_session_id,
    )
    if v:
        call.domain = v.domain
        call.couch_recipient_doc_type = v.owner_doc_type
        call.couch_recipient = v.owner_id
    call.save()


def incoming(phone_number, gateway_session_id, ivr_event, backend=None, input_data=None,
        duration=None):
    """
    The main entry point for all incoming IVR requests.
    """
    call = Call.by_gateway_session_id(gateway_session_id)
    logged_subevent = None
    if call and call.messaging_subevent_id:
        logged_subevent = MessagingSubEvent.objects.get(
            pk=call.messaging_subevent_id)

    if call:
        add_metadata(call, duration)

    if call and call.form_unique_id is None:
        # If this request is for a call with no form,
        # then just short circuit everything and hang up
        return hang_up_response(gateway_session_id, backend=backend)

    if call and backend:
        return handle_known_call_session(call, backend, ivr_event,
            input_data=input_data, logged_subevent=logged_subevent)
    else:
        if not call:
            log_call(phone_number, gateway_session_id, backend=backend)
        return hang_up_response(gateway_session_id, backend=backend)


def get_ivr_backend(recipient, verified_number=None, unverified_number=None):
    if verified_number and verified_number.ivr_backend_id:
        return SQLMobileBackend.load_by_name(
            SQLMobileBackend.IVR,
            verified_number.domain,
            verified_number.ivr_backend_id
        )
    else:
        phone_number = (verified_number.phone_number if verified_number
            else unverified_number)
        phone_number = strip_plus(str(phone_number))
        prefixes = settings.IVR_BACKEND_MAP.keys()
        prefixes = sorted(prefixes, key=lambda x: len(x), reverse=True)
        for prefix in prefixes:
            if phone_number.startswith(prefix):
                return SQLMobileBackend.get_global_backend_by_name(
                    SQLMobileBackend.IVR,
                    settings.IVR_BACKEND_MAP[prefix]
                )
    return None


def log_error(error, call_log_entry=None, logged_subevent=None,
        additional_error_text=None):
    if call_log_entry:
        call_log_entry.error = True
        call_log_entry.error_message = dict(MessagingEvent.ERROR_MESSAGES).get(error)
        if additional_error_text:
            call_log_entry.error_message += ' %s' % additional_error_text
        call_log_entry.save()
    if logged_subevent:
        logged_subevent.error(error, additional_error_text=additional_error_text)


def log_touchforms_error(touchforms_error, call_log_entry=None, logged_subevent=None):
    """
    touchforms_error should be an instance of TouchformsError
    """
    additional_error_text = touchforms_error.response_data.get('human_readable_message', None)
    log_error(MessagingEvent.ERROR_TOUCHFORMS_ERROR,
        call_log_entry, logged_subevent, additional_error_text)


def get_first_ivr_response_data(recipient, call_log_entry, logged_subevent):
    """
    As long as the form has at least one question in it (i.e., it
    doesn't consist of all labels), then we can start the touchforms
    session now and cache the first IVR response, so that all we
    need to do later is serve it up. This makes for less time ringing
    when the user is on the phone, waiting for the line to pick up.

    If the form consists of all labels, we don't do anything here,
    because then we would end up submitting the form right away
    regardless of whether the user actually got the call.

    Returns (ivr_data, error) where ivr_data is an instance of IVRResponseData
    """
    app, module, form, error = get_app_module_form(call_log_entry,
        logged_subevent)
    if error:
        return (None, True)

    if form_requires_input(form):
        session, responses, error = start_call_session(recipient, call_log_entry,
            logged_subevent, app, module, form)
        if error:
            return (None, True)

        ivr_responses = []
        for response in responses:
            ivr_responses.append(format_ivr_response(response.event.caption, app))

        ivr_data = IVRResponseData(ivr_responses, get_input_length(responses[-1]),
            session)
        return (ivr_data, False)

    return (None, False)


def initiate_outbound_call(recipient, form_unique_id, submit_partial_form,
        include_case_side_effects, max_question_retries, messaging_event_id,
        verified_number=None, unverified_number=None, case_id=None,
        case_for_case_submission=False, timestamp=None):
    """
    Returns False if an error occurred and the call should be retried.
    Returns True if the call should not be retried (either because it was
    queued successfully or because an unrecoverable error occurred).
    """
    call = None
    logged_event = MessagingEvent.objects.get(pk=messaging_event_id)
    logged_subevent = logged_event.create_ivr_subevent(recipient,
        form_unique_id, case_id=case_id)

    if not verified_number and not unverified_number:
        log_error(MessagingEvent.ERROR_NO_PHONE_NUMBER,
            logged_subevent=logged_subevent)
        return True

    backend = get_ivr_backend(recipient, verified_number, unverified_number)
    if not backend:
        log_error(MessagingEvent.ERROR_NO_SUITABLE_GATEWAY,
            logged_subevent=logged_subevent)
        return True

    phone_number = (verified_number.phone_number if verified_number
        else unverified_number)

    call = Call(
        couch_recipient_doc_type=recipient.doc_type,
        couch_recipient=recipient.get_id,
        phone_number='+%s' % str(phone_number),
        direction=OUTGOING,
        date=timestamp or datetime.utcnow(),
        domain=recipient.domain,
        form_unique_id=form_unique_id,
        submit_partial_form=submit_partial_form,
        include_case_side_effects=include_case_side_effects,
        max_question_retries=max_question_retries,
        current_question_retry_count=0,
        case_id=case_id,
        case_for_case_submission=case_for_case_submission,
        messaging_subevent_id=logged_subevent.pk,
    )

    ivr_data = None
    if backend.cache_first_ivr_response():
        ivr_data, error = get_first_ivr_response_data(recipient,
            call, logged_subevent)
        if error:
            return True

    if ivr_data:
        logged_subevent.xforms_session = ivr_data.session
        logged_subevent.save()

    try:
        call.backend_api = backend.get_api_id()
        call.backend_id = backend.couch_id
        result = backend.initiate_outbound_call(call, logged_subevent)
        if ivr_data and not call.error:
            backend.set_first_ivr_response(call, call.gateway_session_id, ivr_data)
        call.save()
        logged_subevent.completed()
        return result
    except GatewayConnectionError:
        log_error(MessagingEvent.ERROR_GATEWAY_ERROR, call, logged_subevent)
        raise
    except Exception:
        log_error(MessagingEvent.ERROR_INTERNAL_SERVER_ERROR, call, logged_subevent)
        raise
