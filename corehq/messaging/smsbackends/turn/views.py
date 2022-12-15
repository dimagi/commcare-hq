import json
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.turn.models import SQLTurnWhatsAppBackend
from django.http import HttpResponse


class TurnIncomingSMSView(IncomingBackendView):
    urlname = 'turn_sms'

    @property
    def backend_class(self):
        return SQLTurnWhatsAppBackend

    def post(self, request, api_key, *args, **kwargs):
        request_body = json.loads(request.body)
        for message in request_body.get('messages', []):
            message_id = message.get('id')
            from_ = message.get('from')

            body = None
            if message.get('type') == 'text':
                body = message.get('text', {}).get('body')
            elif message.get('type') == 'image':
                body = message.get('image', {}).get('caption')  # this doesn't seem to work yet

            incoming_sms(
                from_,
                body,
                SQLTurnWhatsAppBackend.get_api_id(),
                backend_message_id=message_id,
                domain_scope=self.domain,
                backend_id=self.backend_couch_id
            )

        return HttpResponse("")
