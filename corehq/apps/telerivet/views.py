from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.telerivet.models import TelerivetBackend

EVENT_INCOMING = "incoming_message"
MESSAGE_TYPE_SMS = "sms"
MESSAGE_TYPE_MMS = "mms"
MESSAGE_TYPE_USSD = "ussd"
MESSAGE_TYPE_CALL = "call"

@require_POST
@csrf_exempt
def incoming_message(request):
    event = request.POST.get("event")
    message_id = request.POST.get("id")
    message_type = request.POST.get("message_type")
    from_number = request.POST.get("from_number")
    contact_id = request.POST.get("contact_id")
    phone_id = request.POST.get("phone_id")
    to_number = request.POST.get("to_number")
    time_created = request.POST.get("time_created")
    time_sent = request.POST.get("time_sent")
    content = request.POST.get("content")
    project_id = request.POST.get("project_id")
    secret = request.POST.get("secret")
    
    backend = TelerivetBackend.by_webhook_secret(secret)
    if backend is None:
        return HttpResponse(status=404)
    
    if event == EVENT_INCOMING:
        if message_type == MESSAGE_TYPE_SMS:
            incoming_sms(from_number, content, TelerivetBackend.get_api_id())
    
    return HttpResponse()

