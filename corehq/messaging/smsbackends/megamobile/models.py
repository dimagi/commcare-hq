import logging
from urllib import urlencode, quote
from urllib2 import urlopen
from corehq.apps.sms.util import strip_plus
from corehq.apps.sms.models import SQLSMSBackend
from dimagi.ext.couchdbkit import *
from corehq.messaging.smsbackends.megamobile.forms import MegamobileBackendForm
from django.conf import settings

DEFAULT_PID = "0"

class MegamobileException(Exception):
    pass


class SQLMegamobileBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'api_account_name',
            'source_identifier',
        ]

    @classmethod
    def get_api_id(cls):
        return 'MEGAMOBILE'

    @classmethod
    def get_generic_name(cls):
        return "Megamobile"

    @classmethod
    def get_form_class(cls):
        return MegamobileBackendForm

    def send(self, msg, *args, **kwargs):
        phone_number = strip_plus(msg.phone_number)
        if not phone_number.startswith('63'):
            raise MegamobileException("Only Filipino phone numbers are supported")

        phone_number = phone_number[2:]
        text = msg.text.encode('utf-8')
        pid = DEFAULT_PID

        config = self.config
        params = urlencode({
            "pid": pid,
            "cel": phone_number,
            "msg": text,
            "src": config.source_identifier,
        })
        api_account_name = quote(config.api_account_name)
        url = 'http://api.mymegamobile.com/%s?%s' % (api_account_name, params)
        response = urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read()
