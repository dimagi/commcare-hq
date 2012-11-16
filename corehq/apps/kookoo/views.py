import sys
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from corehq.apps.ivr.api import incoming, IVR_EVENT_NEW_CALL, IVR_EVENT_INPUT, IVR_EVENT_DISCONNECT
from corehq.apps.kookoo import api as backend_module
from corehq.apps.sms.models import CallLog

"""
Kookoo invokes this view for its main communication with HQ.
Point Kookoo's 'url' parameter here.
"""
@csrf_exempt
def ivr(request):
    # Retrieve all parameters
    called_number = request.GET.get("called_number", None)
    outbound_sid = request.GET.get("outbound_sid", None)
    cid = request.GET.get("cid", None) # This is the caller id, format being 0..., not 91...
    sid = request.GET.get("sid", None)
    operator = request.GET.get("operator", None)
    circle = request.GET.get("circle", None)
    event = request.GET.get("event", None)
    data = request.GET.get("data", None)
    
    phone_number = cid
    if phone_number is not None and phone_number.startswith("0"):
        phone_number = "91" + phone_number[1:]
    
    gateway_session_id = "KOOKOO-" + sid
    
    # Process the event
    if event == "NewCall":
        ivr_event = IVR_EVENT_NEW_CALL
    elif event == "GotDTMF":
        ivr_event = IVR_EVENT_INPUT
    elif event == "Disconnect":
        ivr_event = IVR_EVENT_DISCONNECT
    else:
        ivr_event = IVR_EVENT_DISCONNECT
    
    return incoming(phone_number, backend_module, gateway_session_id, ivr_event, input_data=data)

"""
Kookoo invokes this view after a call is finished (whether answered or not) with status and some statistics.
Point Kookoo's 'callback_url' parameter here.
"""
@csrf_exempt
def ivr_finished(request):
    # Retrieve all parameters
    status = request.POST.get("status", None)
    start_time = request.POST.get("start_time", None)
    caller_id = request.POST.get("caller_id", None)
    phone_no = request.POST.get("phone_no", None)
    sid = request.POST.get("sid", "")
    duration = request.POST.get("duration", None)
    ringing_time = request.POST.get("ringing_time", None)
    status_details = request.POST.get("status_details", None)
    
    gateway_session_id = "KOOKOO-" + sid
    
    call_log_entry = CallLog.view("sms/call_by_session",
                                  startkey=[gateway_session_id, {}],
                                  endkey=[gateway_session_id],
                                  descending=True,
                                  include_docs=True,
                                  limit=1).one()
    if call_log_entry is not None:
        try:
            duration = int(duration)
        except Exception:
            duration = None
        call_log_entry.answered = (status == "answered")
        call_log_entry.duration = duration
        call_log_entry.save()
    
    return HttpResponse("")



