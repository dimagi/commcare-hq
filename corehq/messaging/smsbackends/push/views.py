from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.api import incoming
from corehq.apps.sms.views import IncomingBackendView
from corehq.messaging.smsbackends.push.models import PushBackend
from django.http import HttpResponse, HttpResponseBadRequest
from lxml import etree
from xml.sax.saxutils import unescape
import six


class PushIncomingView(IncomingBackendView):
    urlname = 'push_sms_in'

    @property
    def backend_class(self):
        return PushBackend

    def clean_value(self, value):
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        if isinstance(value, six.text_type):
            return unescape(value.strip())
        return value

    def get_number_and_message(self, request):
        number = None
        text = None
        try:
            xml = etree.fromstring(request.body)
        except etree.XMLSyntaxError:
            return None, None

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
            domain_scope=self.domain,
            backend_id=self.backend_couch_id
        )
        return HttpResponse("OK")
