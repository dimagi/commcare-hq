from corehq.apps.ivr.api import log_call
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.messaging.smsbackends.twilio.models import TwilioBackend
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

EMPTY_RESPONSE = """<?xml version="1.0" encoding="UTF-8" ?>
<Response></Response>"""

IVR_RESPONSE = """<?xml version="1.0" encoding="UTF-8" ?>
<Response>
    <Pause length="30" />
    <Reject />
</Response>"""

API_ID = TwilioBackend.get_api_id()


@csrf_exempt
def sms_in(request):
    if request.method == "POST":
        message_sid = request.POST.get("MessageSid")
        account_sid = request.POST.get("AccountSid")
        from_ = request.POST.get("From")
        to = request.POST.get("To")
        body = request.POST.get("Body")
        incoming_sms(
            from_,
            body,
            TwilioBackend.get_api_id(),
            backend_message_id=message_sid
        )
        return HttpResponse(EMPTY_RESPONSE)
    else:
        return HttpResponseBadRequest("POST Expected")


@csrf_exempt
def ivr_in(request):
    if request.method == 'POST':
        from_number = request.POST.get('From')
        call_sid = request.POST.get('CallSid')
        log_call(from_number, '%s-%s' % (API_ID, call_sid))
        return HttpResponse(IVR_RESPONSE)
    else:
        return HttpResponseBadRequest("POST Expected")
