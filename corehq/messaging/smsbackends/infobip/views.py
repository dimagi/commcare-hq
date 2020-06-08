import json
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.infobip.models import SQLInfobipBackend
from django.http import HttpResponse


class InfobipIncomingMessageView(IncomingBackendView):
    urlname = 'infobip_sms'

    @property
    def backend_class(self):
        return SQLInfobipBackend

    def post(self, request, api_key, *args, **kwargs):
        request_body = json.loads(request.body)
        for message in request_body.get('results'):
            message_sid = message.get('messageId')
            from_ = message.get('from')
            message_content = message.get('message')
            if message_content.get('type') == 'TEXT':
                body = message_content.get('text', {})
            elif message_content.get('type') in ['IMAGE', 'AUDIO', 'VIDEO', 'DOCUMENT']:
                body = message_content.get('caption', {})

            incoming_sms(
                from_,
                body,
                SQLInfobipBackend.get_api_id(),
                backend_message_id=message_sid,
                domain_scope=self.domain,
                backend_id=self.backend_couch_id
            )
        return HttpResponse("")
