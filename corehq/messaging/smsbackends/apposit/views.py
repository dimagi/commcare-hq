from __future__ import absolute_import
from __future__ import unicode_literals
import json
from corehq.apps.sms.api import incoming
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.apposit.models import SQLAppositBackend
from django.http import HttpResponse, HttpResponseBadRequest


class AppositIncomingView(IncomingBackendView):
    urlname = 'apposit_incoming'

    @property
    def backend_class(self):
        return SQLAppositBackend

    def post(self, request, api_key, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except:
            return HttpResponseBadRequest("Expected valid JSON as HTTP request body")

        from_number = data.get('from')
        message = data.get('message')
        message_id = data.get('messageId')

        if not from_number or not message:
            return HttpResponseBadRequest("Missing 'from' or 'message'")

        incoming(
            from_number,
            message,
            SQLAppositBackend.get_api_id(),
            backend_message_id=message_id,
            domain_scope=self.domain,
            backend_id=self.backend_couch_id
        )
        return HttpResponse("")
