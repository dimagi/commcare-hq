from django.http import HttpResponse
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.yo.models import SQLYoBackend


def sms_in(request, backend_id=None):
    dest = request.GET.get("dest")
    sender = request.GET.get("sender")
    message = request.GET.get("message")
    incoming_sms(sender, message, SQLYoBackend.get_api_id(), backend_id=backend_id)
    return HttpResponse("OK")


class YoIncomingSMSView(IncomingBackendView):
    urlname = 'yo_sms'

    @property
    def backend_class(self):
        return SQLYoBackend

    def get(self, request, api_key, *args, **kwargs):
        return sms_in(request, backend_id=self.backend_couch_id)
