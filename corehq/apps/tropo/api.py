import logging
from urllib import urlencode
from urllib2 import urlopen
from corehq.apps.sms.util import create_billable_for_sms, clean_phone_number
from corehq.apps.sms.mixin import SMSBackend
from couchdbkit.ext.django.schema import *
from corehq.apps.tropo.forms import TropoBackendForm

class TropoBackend(SMSBackend):
    messaging_token = StringProperty()

    @classmethod
    def get_api_id(cls):
        return "TROPO"

    @classmethod
    def get_generic_name(cls):
        return "Tropo"

    @classmethod
    def get_template(cls):
        return "tropo/backend.html"

    @classmethod
    def get_form_class(cls):
        return TropoBackendForm

    def send(self, msg, delay=True, *args, **kwargs):
        phone_number = clean_phone_number(msg.phone_number)
        text = msg.text.encode("utf-8")
        params = urlencode({
            "action" : "create",
            "token" : self.messaging_token,
            "numberToDial" : phone_number,
            "msg" : text,
            "_send_sms" : "true",
        })
        url = "https://api.tropo.com/1.0/sessions?%s" % params
        response = urlopen(url).read()

        create_billable_for_sms(msg, TropoBackend.get_api_id(), delay=delay, response=response)

        return response

