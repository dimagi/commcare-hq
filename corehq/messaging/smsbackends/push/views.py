from corehq.apps.sms.api import incoming
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.push.models import PushBackend
from django.http import HttpResponse, HttpResponseBadRequest

from defusedxml.minidom import parseString
from xml.dom import Node
from xml.parsers.expat import ExpatError
from xml.sax.saxutils import unescape


class PushIncomingView(IncomingBackendView):
    urlname = 'push_sms_in'

    @property
    def backend_class(self):
        return PushBackend

    def clean_value(self, value):
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        if isinstance(value, str):
            return unescape(value.strip())
        return value

    def get_number_and_message(self, request):
        number = None
        text = None
        try:
            xml = parseString(request.body).documentElement.childNodes
        except (ExpatError, ValueError):
            return None, None

        for element in xml:
            if element.nodeType == Node.ELEMENT_NODE:
                name = element.getAttribute('name')
                if name == 'MobileNumber':
                    number = self.clean_value(element.childNodes[0].nodeValue)
                elif name == 'Text':
                    text = self.clean_value(element.childNodes[0].nodeValue)

        return number, text

    def post(self, request, api_key, *args, **kwargs):
        number, text = self.get_number_and_message(request)
        if not number or not text:
            return HttpResponseBadRequest("MobileNumber or Text are missing")

        incoming(
            number,
            text,
            PushBackend.get_api_id(),
            domain_scope=self.domain,
            backend_id=self.backend_couch_id
        )
        return HttpResponse("OK")
