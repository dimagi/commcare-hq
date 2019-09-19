from django.http import HttpResponse
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend
from corehq.messaging.smsbackends.sislog.util import convert_raw_string


def sms_in(request, backend_id=None):
    """
    sender - the number of the person sending the sms
    receiver - the number the sms was sent to
    msgdata - the message
    """
    sender = request.GET.get("sender", None)
    receiver = request.GET.get("receiver", None)
    msgdata = request.GET.get("msgdata", None)
    if sender is None or msgdata is None:
        return HttpResponse(status=400)
    else:
        cleaned_text = convert_raw_string(msgdata)
        incoming_sms(sender, cleaned_text, SQLSislogBackend.get_api_id(), raw_text=msgdata, backend_id=backend_id)
        return HttpResponse()


class SislogIncomingSMSView(IncomingBackendView):
    urlname = 'sislog_sms'

    @property
    def backend_class(self):
        return SQLSislogBackend

    def get(self, request, api_key, *args, **kwargs):
        return sms_in(request, backend_id=self.backend_couch_id)
