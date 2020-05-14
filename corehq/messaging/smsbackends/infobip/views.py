from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.infobip.models import SQLInfobipBackend
from django.http import HttpResponse


EMPTY_RESPONSE = ""


class InfobipIncomingMessageView(IncomingBackendView):
    urlname = 'infobip_message'

    @property
    def backend_class(self):
        return SQLInfobipBackend

    def post(self, request, api_key, *args, **kwargs):
        results = request.POST.get('results')
        message = results[0]
        from_ = message['from']
        message_sid = message['messageId']
        body = message['message']['text']

        incoming_sms(
            from_,
            body,
            SQLInfobipBackend.get_api_id(),
            backend_message_id=message_sid,
            domain_scope=self.domain,
            backend_id=self.backend_couch_id
        )
        return HttpResponse(EMPTY_RESPONSE)
