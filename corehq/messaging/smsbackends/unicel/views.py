from django.http import HttpResponse
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.unicel.models import create_from_request, SQLUnicelBackend
import json


def incoming(request, backend_id=None):
    """
    The inbound endpoint for UNICEL's API.
    """
    # for now just save this information in the message log and return
    message = create_from_request(request, backend_id=backend_id)
    return HttpResponse(json.dumps({'status': 'success', 'message_id': message.couch_id}), 'text/json')


class UnicelIncomingSMSView(IncomingBackendView):
    urlname = 'unicel_sms'

    @property
    def backend_class(self):
        return SQLUnicelBackend

    def get(self, request, api_key, *args, **kwargs):
        return incoming(request, backend_id=self.backend_couch_id)
