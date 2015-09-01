from urllib import urlencode
from urllib2 import urlopen
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.mixin import SMSBackend
from dimagi.ext.couchdbkit import *
from commcarehq.messaging.smsbackends.tropo.forms import TropoBackendForm
from django.conf import settings

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

    def get_sms_interval(self):
        return 1

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
        response = urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read()
        return response

