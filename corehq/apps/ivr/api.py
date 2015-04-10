from datetime import datetime
from corehq.apps.sms.models import CallLog, INCOMING, OUTGOING
from corehq.apps.sms.mixin import VerifiedNumber, MobileBackend
from corehq.apps.sms.util import strip_plus
from corehq.apps.smsforms.app import start_session, _get_responses
from corehq.apps.smsforms.models import XFORMS_SESSION_IVR, get_session_by_session_id
from corehq.apps.app_manager.models import Form
from corehq.apps.hqmedia.models import HQMediaMapItem
from django.http import HttpResponse
from django.conf import settings
from dimagi.utils.web import get_url_base
from touchforms.formplayer.api import current_question
from corehq.apps.smsforms.app import submit_unfinished_form

IVR_EVENT_NEW_CALL = "NEW_CALL"
IVR_EVENT_INPUT = "INPUT"
IVR_EVENT_DISCONNECT = "DISCONNECT"

def convert_media_path_to_hq_url(path, app):
    media = app.multimedia_map.get(path, None)
    if media is None:
        return None
    else:
        url_base = get_url_base()
        return url_base + HQMediaMapItem.format_match_map(path, media_type=media.media_type, media_id=media.multimedia_id)["url"] + "foo.wav"

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


def hang_up_response(gateway_session_id, backend_module=None):
    if backend_module:
        return HttpResponse(backend_module.get_http_response_string(
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


def incoming(phone_number, backend_module, gateway_session_id, ivr_event, input_data=None,
    duration=None):
    # Look up the call if one already exists
    call_log_entry = CallLog.view("sms/call_by_session",
                                  startkey=[gateway_session_id, {}],
                                  endkey=[gateway_session_id],
                                  descending=True,
                                  include_docs=True,
                                  limit=1).one()
    
    answer_is_valid = False # This will be set to True if IVR validation passes
    error_occurred = False # This will be set to False if touchforms validation passes (i.e., no form constraints fail)

    if call_log_entry:
        add_metadata(call_log_entry, duration)

    if call_log_entry and call_log_entry.form_unique_id is None:
        # If this request is for a call with no touchforms session,
        # then just short circuit everything and hang up
        return hang_up_response(gateway_session_id, backend_module=backend_module)

    if call_log_entry is not None and backend_module:
        if ivr_event == IVR_EVENT_NEW_CALL and call_log_entry.use_precached_first_response:
            return HttpResponse(call_log_entry.first_response)
        
        form = Form.get_form(call_log_entry.form_unique_id)
        app = form.get_app()
        module = form.get_module()
        recipient = call_log_entry.recipient
        
        if ivr_event == IVR_EVENT_NEW_CALL:
            case_id = call_log_entry.case_id
            case_for_case_submission = call_log_entry.case_for_case_submission
            session, responses = start_session(recipient.domain, recipient, app,
                module, form, case_id, yield_responses=True,
                session_type=XFORMS_SESSION_IVR,
                case_for_case_submission=case_for_case_submission)
            call_log_entry.xforms_session_id = session.session_id
        elif ivr_event == IVR_EVENT_INPUT:
            if call_log_entry.xforms_session_id is not None:
                current_q = current_question(call_log_entry.xforms_session_id)
                if validate_answer(input_data, current_q):
                    answer_is_valid = True
                    responses = _get_responses(recipient.domain, recipient._id, input_data, yield_responses=True, session_id=call_log_entry.xforms_session_id)
                else:
                    call_log_entry.current_question_retry_count += 1
                    responses = [current_q]
            else:
                responses = []
        else:
            responses = []
        
        ivr_responses = []
        hang_up = False
        for response in responses:
            if response.is_error:
                error_occurred = True
                call_log_entry.current_question_retry_count += 1
                if response.text_prompt is None:
                    ivr_responses = []
                    break
                else:
                    ivr_responses.append(format_ivr_response(response.text_prompt, app))
            elif response.event.type == "question":
                ivr_responses.append(format_ivr_response(response.event.caption, app))
            elif response.event.type == "form-complete":
                hang_up = True
        
        if answer_is_valid and not error_occurred:
            call_log_entry.current_question_retry_count = 0
        
        if call_log_entry.max_question_retries is not None and call_log_entry.current_question_retry_count > call_log_entry.max_question_retries:
            # Force hang-up
            ivr_responses = []
        
        if len(ivr_responses) == 0:
            hang_up = True
        
        input_length = None
        
        if hang_up:
            if call_log_entry.xforms_session_id is not None:
                # Process disconnect
                session = get_session_by_session_id(call_log_entry.xforms_session_id)
                if session.end_time is None:
                    if call_log_entry.submit_partial_form:
                        submit_unfinished_form(session.session_id, call_log_entry.include_case_side_effects)
                    else:
                        session.end(completed=False)
                        session.save()
        else:
            # Set input_length to let the ivr gateway know how many digits we need to collect.
            # Have to get the current question again, since the last XFormsResponse in responses
            # may not have an event if it was a response to a constraint error.
            if error_occurred:
                current_q = current_question(call_log_entry.xforms_session_id)
            else:
                current_q = responses[-1]
            
            input_length = get_input_length(current_q)
        
        call_log_entry.save()
        return HttpResponse(backend_module.get_http_response_string(gateway_session_id, ivr_responses, collect_input=(not hang_up), hang_up=hang_up, input_length=input_length))
    
    # If not processed, just log the call

    if call_log_entry:
        # No need to log, already exists
        return HttpResponse("")

    cleaned_number = phone_number
    if cleaned_number is not None and len(cleaned_number) > 0 and cleaned_number[0] == "+":
        cleaned_number = cleaned_number[1:]
    
    # Try to look up the verified number entry
    v = VerifiedNumber.view("sms/verified_number_by_number",
        key=cleaned_number,
        include_docs=True
    ).one()
    
    # If none was found, try to match only the last digits of numbers in the database
    if v is None:
        v = VerifiedNumber.view("sms/verified_number_by_suffix",
            key=cleaned_number,
            include_docs=True
        ).one()
    
    # Save the call entry
    msg = CallLog(
        phone_number=cleaned_number,
        direction=INCOMING,
        date=datetime.utcnow(),
        backend_api=backend_module.API_ID if backend_module else None,
        gateway_session_id=gateway_session_id,
    )
    if v is not None:
        msg.domain = v.domain
        msg.couch_recipient_doc_type = v.owner_doc_type
        msg.couch_recipient = v.owner_id
    msg.save()

    return hang_up_response(gateway_session_id, backend_module=backend_module)


def get_ivr_backend(recipient, verified_number=None, unverified_number=None):
    if verified_number and verified_number.ivr_backend_id:
        return MobileBackend.get(verified_number.ivr_backend_id)
    else:
        phone_number = (verified_number.phone_number if verified_number
            else unverified_number)
        phone_number = strip_plus(str(phone_number))
        prefixes = settings.IVR_BACKEND_MAP.keys()
        prefixes = sorted(prefixes, key=lambda x: len(x), reverse=True)
        for prefix in prefixes:
            if phone_number.startswith(prefix):
                return MobileBackend.get(settings.IVR_BACKEND_MAP[prefix])
    return None

def initiate_outbound_call(recipient, form_unique_id, submit_partial_form,
    include_case_side_effects, max_question_retries, verified_number=None,
    unverified_number=None, case_id=None, case_for_case_submission=False,
    timestamp=None):
    """
    Returns True if the call was queued successfully, or False if an error
    occurred.
    """
    call_log_entry = None
    try:
        if not verified_number and not unverified_number:
            return False
        phone_number = (verified_number.phone_number if verified_number
            else unverified_number)
        call_log_entry = CallLog(
            couch_recipient_doc_type=recipient.doc_type,
            couch_recipient=recipient.get_id,
            phone_number="+%s" % str(phone_number),
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
        )
        backend = get_ivr_backend(recipient, verified_number, unverified_number)
        if not backend:
            return False
        kwargs = backend.get_cleaned_outbound_params()
        module = __import__(backend.outbound_module,
            fromlist=["initiate_outbound_call"])
        call_log_entry.backend_api = module.API_ID
        call_log_entry.save()
        return module.initiate_outbound_call(call_log_entry, **kwargs)
    except Exception:
        if call_log_entry:
            call_log_entry.error = True
            call_log_entry.error_message = "Internal Server Error"
            call_log_entry.save()
        raise

