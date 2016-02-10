from corehq.apps.sms.api import incoming
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.apposit.models import SQLAppositBackend
from django.http import HttpResponse, HttpResponseBadRequest


class AppositIncomingView(IncomingBackendView):
    urlname = 'apposit_incoming'

    def get(self, request, api_key, *args, **kwargs):
        return HttpResponseBadRequest("ERROR: Expected POST")

    def post(self, request, api_key, *args, **kwargs):
        fromAddress = request.POST.get('fromAddress')
        toAddress = request.POST.get('toAddress')
        channel = request.POST.get('channel')
        content = request.POST.get('content')

        if channel != 'SMS':
            # We don't support any other services yet
            return HttpResponse("")

        if not fromAddress or not content:
            return HttpResponseBadRequest("ERROR: Missing fromAddress or content")

        incoming(fromAddress, content, SQLAppositBackend.get_api_id())
        return HttpResponse("")
