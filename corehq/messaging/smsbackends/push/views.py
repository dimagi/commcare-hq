from corehq.apps.sms.api import incoming
from corehq.apps.sms.views import NewIncomingBackendView
from corehq.messaging.smsbackends.push.models import PushBackend
from django.http import HttpResponse, HttpResponseBadRequest
from lxml import etree


class PushIncomingView(NewIncomingBackendView):
    urlname = 'push_sms_in'

    @property
    def backend_class(self):
        return PushBackend

    def clean_value(self, value):
        if isinstance(value, basestring):
            return value.strip()

        return value

    def get_number_and_message(self, request):
        number = None
        text = None
        xml = etree.fromstring(request.body)
        for element in xml:
            name = element.get('name')
            if name == 'MobileNumber':
                number = self.clean_value(element.text)
            elif name == 'Text':
                text = self.clean_value(element.text)

        return number, text

    def post(self, request, api_key, *args, **kwargs):
        number, text = self.get_number_and_message(request)
        if not number or not text:
            return HttpResponseBadRequest("MobileNumber or Text are missing")

        incoming(
            number,
            text,
            PushBackend.get_api_id(),
            backend_id=self.backend_couch_id
        )
        return HttpResponse("OK")
