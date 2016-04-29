from urllib import urlencode
from urllib2 import urlopen
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.models import SQLSMSBackend
from dimagi.ext.couchdbkit import *
from corehq.messaging.smsbackends.tropo.forms import TropoBackendForm
from django.conf import settings


class SQLTropoBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'messaging_token',
        ]

    @classmethod
    def get_api_id(cls):
        return 'TROPO'

    @classmethod
    def get_generic_name(cls):
        return "Tropo"

    @classmethod
    def get_form_class(cls):
        return TropoBackendForm

    def get_sms_rate_limit(self):
        return 60

    @classmethod
    def get_opt_in_keywords(cls):
        return ['START']

    @classmethod
    def get_opt_out_keywords(cls):
        return ['STOP']

    def send(self, msg, *args, **kwargs):
        phone_number = clean_phone_number(msg.phone_number)
        text = msg.text.encode('utf-8')
        config = self.config
        params = urlencode({
            'action': 'create',
            'token': config.messaging_token,
            'numberToDial': phone_number,
            'msg': text,
            '_send_sms': 'true',
        })
        url = 'https://api.tropo.com/1.0/sessions?%s' % params
        response = urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read()
        return response
