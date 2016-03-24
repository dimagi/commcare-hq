from datetime import datetime
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from corehq.apps.ivr.api import incoming, IVR_EVENT_NEW_CALL, IVR_EVENT_INPUT, IVR_EVENT_DISCONNECT
from corehq.apps.ivr.models import Call
from corehq.apps.sms.models import SQLMobileBackend
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.cache.cache_core import get_redis_client


@csrf_exempt
def ivr(request):
    """
    Kookoo invokes this view for its main communication with HQ.
    Point Kookoo's 'url' parameter here.
    """
    # Retrieve all parameters
    called_number = request.GET.get("called_number", None)
    outbound_sid = request.GET.get("outbound_sid", None)
    cid = request.GET.get("cid", None) # This is the caller id, format being 0..., not 91...
    sid = request.GET.get("sid", None)
    operator = request.GET.get("operator", None)
    circle = request.GET.get("circle", None)
    event = request.GET.get("event", None)
    data = request.GET.get("data", None)
    total_call_duration = request.GET.get("total_call_duration", None)
    
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

    backend = SQLMobileBackend.get_global_backend_by_name(
        SQLMobileBackend.IVR,
        'MOBILE_BACKEND_KOOKOO'
    )
    with CriticalSection([gateway_session_id], timeout=300):
        result = incoming(phone_number, gateway_session_id, ivr_event,
            backend=backend, input_data=data, duration=total_call_duration)
    return result


def log_metadata_received(call):
    """
    Only temporary, for debugging.
    """
    try:
        key = 'kookoo-metadata-received-%s' % call.pk
        client = get_redis_client()
        client.set(key, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        client.expire(key, 7 * 24 * 60 * 60)
    except:
        pass


@csrf_exempt
def ivr_finished(request):
    """
    Kookoo invokes this view after a call is finished (whether answered or not)
    with status and some statistics.
    Point Kookoo's 'callback_url' parameter here.
    """
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

    with CriticalSection([gateway_session_id], timeout=300):
        call = Call.by_gateway_session_id(gateway_session_id)
        if call:
            log_metadata_received(call)
            try:
                duration = int(duration)
            except Exception:
                duration = None
            call.answered = (status == 'answered')
            call.duration = duration
            call.save()

    return HttpResponse('')
