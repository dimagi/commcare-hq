from corehq.apps.sms.api import incoming
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.smsgh.models import SQLSMSGHBackend
from django.http import HttpResponse, HttpResponseBadRequest


class SMSGHIncomingView(IncomingBackendView):
    urlname = 'smsgh_sms_in'

    def get(self, request, api_key, *args, **kwargs):
        msg = request.GET.get('msg', None)
        snr = request.GET.get('snr', None)
        # We don't have a place to put this right now, but leaving it here
        # so we remember the parameter name in case we need it later
        to = request.GET.get('to', None)

        if not msg or not snr:
            return HttpResponseBadRequest("ERROR: Missing msg or snr")

        incoming(snr, msg, SQLSMSGHBackend.get_api_id())
        return HttpResponse("")

    def post(self, request, api_key, *args, **kwargs):
        return self.get(request, api_key, *args, **kwargs)
