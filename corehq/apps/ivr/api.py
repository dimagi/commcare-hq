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

"""
Return True if answer is a valid response to question, False if not.
(question is the XformsResponse object for the question)
"""
def validate_answer(answer, question):
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

def incoming(phone_number, backend_module, gateway_session_id, ivr_event, input_data=None):
    # Look up the call if one already exists
    call_log_entry = CallLog.view("sms/call_by_session",
                                  startkey=[gateway_session_id, {}],
                                  endkey=[gateway_session_id],
                                  descending=True,
                                  include_docs=True,
                                  limit=1).one()
    
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
            call_log_entry.save()
        elif ivr_event == IVR_EVENT_INPUT:
            if call_log_entry.xforms_session_id is not None:
                current_q = current_question(call_log_entry.xforms_session_id)
                if validate_answer(input_data, current_q):
                    responses = _get_responses(recipient.domain, recipient._id, input_data, yield_responses=True, session_id=call_log_entry.xforms_session_id)
                else:
                    responses = [current_q]
            else:
                responses = []
        else:
            if call_log_entry.xforms_session_id is not None:
                # Hang up and process disconnect
                session = XFormsSession.latest_by_session_id(call_log_entry.xforms_session_id)
                if session.end_time is None:
                    session.end(completed=False)
                    session.save()
            responses = []
        
        ivr_responses = []
        hang_up = False
        for response in responses:
            if response.event.type == "question":
                ivr_responses.append({"text_to_say" : response.event.caption,
                                      "audio_file_url" : convert_media_path_to_hq_url(response.event.caption, app) if response.event.caption.startswith("jr://") else None})
            elif response.event.type == "form-complete":
                hang_up = True
        
        if len(ivr_responses) == 0:
            hang_up = True
        
        if len(responses) > 0 and responses[-1].event.type == "question" and responses[-1].event.datatype == "select":
            input_length = 1
        else:
            input_length = None
        
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

def initiate_outbound_call(verified_number, form_unique_id):
    call_log_entry = CallLog(
        couch_recipient_doc_type = verified_number.owner_doc_type,
        couch_recipient          = verified_number.owner_id,
        phone_number             = "+" + str(verified_number.phone_number),
        direction                = OUTGOING,
        date                     = datetime.utcnow(),
        domain                   = verified_number.domain,
        form_unique_id           = form_unique_id,
    )
    backend = verified_number.ivr_backend
    kwargs = backend.outbound_params
    module = __import__(backend.outbound_module, fromlist=["initiate_outbound_call"])
    call_log_entry.backend_api = module.API_ID
    call_log_entry.save()
    module.initiate_outbound_call(call_log_entry, **kwargs)




