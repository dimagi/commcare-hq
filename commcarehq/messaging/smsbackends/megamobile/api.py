import logging
from urllib import urlencode, quote
from urllib2 import urlopen
from corehq.apps.sms.util import strip_plus
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.models import SMSLog
from dimagi.ext.couchdbkit import *
from commcarehq.messaging.smsbackends.megamobile.forms import MegamobileBackendForm
from django.conf import settings

DEFAULT_PID = "0"

class MegamobileException(Exception):
    pass

class MegamobileBackend(SMSBackend):
    api_account_name = StringProperty()
    source_identifier = StringProperty()

    @classmethod
    def get_api_id(cls):
        return "MEGAMOBILE"

    @classmethod
    def get_generic_name(cls):
        return "Megamobile"

    @classmethod
    def get_template(cls):
        return "megamobile/backend.html"

    @classmethod
    def get_form_class(cls):
        return MegamobileBackendForm

    def send(self, msg, delay=True, *args, **kwargs):
        phone_number = strip_plus(msg.phone_number)
        if not phone_number.startswith("63"):
            raise MegamobileException("Only Filipino phone numbers are supported")
        phone_number = phone_number[2:]

        text = msg.text.encode("utf-8")

        pid = None
        if msg.in_reply_to:
            original_msg = SMSLog.get(msg.in_reply_to)
            pid = getattr(original_msg, "megamobile_pid", None)
        pid = pid or DEFAULT_PID
        setattr(msg, "megamobile_pid", pid)
        msg.save()

        params = urlencode({
            "pid" : pid,
            "cel" : phone_number,
            "msg" : text,
            "src" : self.source_identifier,
        })
        api_account_name = quote(self.api_account_name)
        url = "http://api.mymegamobile.com/%s?%s" % (api_account_name, params)
        response = urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read()

