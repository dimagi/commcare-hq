from datetime import datetime
from corehq.apps.sms.models import CallLog, INCOMING, OUTGOING
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.smsforms.app import start_session, _get_responses
from corehq.apps.smsforms.models import XFormsSession, XFORMS_SESSION_IVR
from corehq.apps.app_manager.models import get_app, Form
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

def incoming(phone_number, backend_module, gateway_session_id, ivr_event, input_data=None):
    # Look up the call if one already exists
    call_log_entry = CallLog.view("sms/call_by_session",
                                  startkey=[gateway_session_id, {}],
                                  endkey=[gateway_session_id],
                                  descending=True,
                                  include_docs=True,
                                  limit=1).one()
    
    answer_is_valid = False # This will be set to True if IVR validation passes
    error_occurred = True # This will be set to False if touchforms validation passes (i.e., no form constraints fail)
    
    if call_log_entry is not None:
        form = Form.get_form(call_log_entry.form_unique_id)
        app = form.get_app()
        module = form.get_module()
        recipient = call_log_entry.recipient
        
        if ivr_event == IVR_EVENT_NEW_CALL:
            if recipient.doc_type == "CommCareCase":
                case_id = recipient._id
            else:
                #TODO: Need a way to choose the case when it's a user that's playing the form
                case_id = None
            
            session, responses = start_session(recipient.domain, recipient, app, module, form, case_id, yield_responses=True, session_type=XFORMS_SESSION_IVR)
            call_log_entry.xforms_session_id = session.session_id
        elif ivr_event == IVR_EVENT_INPUT:
            if call_log_entry.xforms_session_id is not None and (call_log_entry.max_question_retries is None or call_log_entry.current_question_retry_count <= call_log_entry.max_question_retries):
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
            if call_log_entry.xforms_session_id is not None:
                # Hang up and process disconnect
                session = XFormsSession.latest_by_session_id(call_log_entry.xforms_session_id)
                if session.end_time is None:
                    if call_log_entry.submit_partial_form:
                        submit_unfinished_form(session.session_id, call_log_entry.include_case_side_effects)
                    else:
                        session.end(completed=False)
                        session.save()
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
        
        # Set input_length to let the ivr gateway know how many digits we need to collect
        input_length = None
        if len(responses) > 0:
            # Have to get the current question again, since the last XFormsResponse in responses
            # may not have an event if it was a response to a constraint error
            current_q = current_question(call_log_entry.xforms_session_id)
            if current_q.event.type == "question" and current_q.event.datatype == "select":
                input_length = 1
        
        call_log_entry.save()
        return HttpResponse(backend_module.get_http_response_string(gateway_session_id, ivr_responses, collect_input=(not hang_up), hang_up=hang_up, input_length=input_length))
    
    # If not processed, just log the call
    
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
        phone_number    = cleaned_number,
        direction       = INCOMING,
        date            = datetime.utcnow(),
        backend_api     = backend_module.API_ID
    )
    if v is not None:
        msg.domain = v.domain
        msg.couch_recipient_doc_type = v.owner_doc_type
        msg.couch_recipient = v.owner_id
    msg.save()
    
    return HttpResponse("")

def initiate_outbound_call(verified_number, form_unique_id, submit_partial_form, include_case_side_effects, max_question_retries):
    call_log_entry = CallLog(
        couch_recipient_doc_type = verified_number.owner_doc_type,
        couch_recipient          = verified_number.owner_id,
        phone_number             = "+" + str(verified_number.phone_number),
        direction                = OUTGOING,
        date                     = datetime.utcnow(),
        domain                   = verified_number.domain,
        form_unique_id           = form_unique_id,
        submit_partial_form      = submit_partial_form,
        include_case_side_effects = include_case_side_effects,
        max_question_retries     = max_question_retries,
        current_question_retry_count = 0,
    )
    backend = verified_number.ivr_backend
    kwargs = backend.outbound_params
    module = __import__(backend.outbound_module, fromlist=["initiate_outbound_call"])
    call_log_entry.backend_api = module.API_ID
    call_log_entry.save()
    module.initiate_outbound_call(call_log_entry, **kwargs)




