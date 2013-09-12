import urllib2
from corehq.apps.grapevine.forms import GrapevineBackendForm
from corehq.apps.sms.util import create_billable_for_sms, clean_phone_number
from corehq.apps.sms.mixin import SMSBackend
from couchdbkit.ext.django.schema import *
from xml.sax.saxutils import escape

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
    <gviSmsMessage>
        <affiliateCode>{affiliate_code}</affiliateCode>
        <authenticationCode>{auth_code}</authenticationCode>
        <messageType>text</messageType>
        <recipientList>
            <message>{message}</message>
            <recipient>
                <msisdn>{msisdn}</msisdn>
            </recipient>
        </recipientList>
    </gviSmsMessage>"""


class GrapevineBackend(SMSBackend):
    affiliate_code = StringProperty()
    authentication_code = StringProperty()

    @classmethod
    def get_api_id(cls):
        return "GVI"

    @classmethod
    def get_generic_name(cls):
        return "Grapevine"

    @classmethod
    def get_template(cls):
        return "grapevine/backend.html"

    @classmethod
    def get_form_class(cls):
        return GrapevineBackendForm

    def send(self, msg, delay=True, *args, **kwargs):
        phone_number = clean_phone_number(msg.phone_number)
        text = msg.text.encode("utf-8")

        data = TEMPLATE.format(
            affiliate_code=self.affiliate_code,
            auth_cod=self.authentication_code,
            message=escape(text),
            msisdn=phone_number
        )

        # TODO: change to grapevine url
        url = "https://api.tropo.com/1.0/sessions?%s"
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        resp = response.read()
