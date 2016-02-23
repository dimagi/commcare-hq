from corehq.apps.ivr.api import log_call
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.views import NewIncomingBackendView
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt


EMPTY_RESPONSE = """<?xml version="1.0" encoding="UTF-8" ?>
<Response></Response>"""

IVR_RESPONSE = """<?xml version="1.0" encoding="UTF-8" ?>
<Response>
    <Pause length="30" />
    <Reject />
</Response>"""


class TwilioIncomingSMSView(NewIncomingBackendView):
    urlname = 'twilio_sms'

    @property
    def backend_class(self):
        return SQLTwilioBackend

    def post(self, request, api_key, *args, **kwargs):
        message_sid = request.POST.get('MessageSid')
        account_sid = request.POST.get('AccountSid')
        from_ = request.POST.get('From')
        to = request.POST.get('To')
        body = request.POST.get('Body')
        incoming_sms(
            from_,
            body,
            SQLTwilioBackend.get_api_id(),
            backend_message_id=message_sid,
            backend_id=self.backend_couch_id
        )
        return HttpResponse(EMPTY_RESPONSE)


class TwilioIncomingIVRView(NewIncomingBackendView):
    urlname = 'twilio_ivr'

    @property
    def backend_class(self):
        return SQLTwilioBackend

    def post(self, request, api_key, *args, **kwargs):
        from_number = request.POST.get('From')
        call_sid = request.POST.get('CallSid')
        log_call(from_number, '%s-%s' % (SQLTwilioBackend.get_api_id(), call_sid))
        return HttpResponse(IVR_RESPONSE)
