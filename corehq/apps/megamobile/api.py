import logging
from urllib import urlencode
from urllib2 import urlopen
from corehq.apps.sms.util import strip_plus
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.models import SMSLog
from couchdbkit.ext.django.schema import *
from corehq.apps.megamobile.forms import MegamobileBackendForm

class MegamobileException(Exception):
    pass

class MegamobileBackend(SMSBackend):
    default_pid = StringProperty()

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
            pid = getattr(original_msg, "_megamobile_pid", None)
        pid = pid or self.default_pid
        setattr(msg, "_megamobile_pid", pid)
        msg.save()

        params = urlencode({
            "pid" : pid,
            "cel" : phone_number,
            "msg" : text,
        })
        url = "http://api.mymegamobile.com/dimagi?%s" % params
        response = urlopen(url).read()

