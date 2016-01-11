import urllib
from django.conf import settings
import urllib2
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.models import SQLSMSBackend
from dimagi.ext.couchdbkit import *
from corehq.messaging.smsbackends.mach.forms import MachBackendForm

MACH_URL = "http://smsgw.a2p.mme.syniverse.com/sms.php"

class MachBackend(SMSBackend):
    account_id = StringProperty()
    password = StringProperty()
    sender_id = StringProperty()
    # Defines the maximum number of outgoing sms requests to be made per
    # second. This is defined at the account level.
    max_sms_per_second = IntegerProperty(default=1)

    @classmethod
    def get_api_id(cls):
        return "MACH"

    @classmethod
    def get_generic_name(cls):
        return "Syniverse"

    @classmethod
    def get_template(cls):
        return "mach/backend.html"

    @classmethod
    def get_form_class(cls):
        return MachBackendForm

    def get_sms_interval(self):
        return (1.0 / self.max_sms_per_second)

    def send(self, msg, delay=True, *args, **kwargs):
        params = {
            "id" : self.account_id,
            "pw" : self.password,
            "snr" : self.sender_id,
            "dnr" : msg.phone_number,
        }
        try:
            text = msg.text.encode("iso-8859-1")
            params["msg"] = text
        except UnicodeEncodeError:
            params["msg"] = msg.text.encode("utf-16-be").encode("hex")
            params["encoding"] = "ucs"
        url = "%s?%s" % (MACH_URL, urllib.urlencode(params))
        resp = urllib2.urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read()

        return resp

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLMachBackend


class SQLMachBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def _migration_get_couch_model_class(cls):
        return MachBackend

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'account_id',
            'password',
            'sender_id',
            # Defines the maximum number of outgoing sms requests to be made per
            # second. This is defined at the account level.
            'max_sms_per_second',
        ]

    @classmethod
    def get_api_id(cls):
        return 'MACH'

    @classmethod
    def get_generic_name(cls):
        return "Syniverse"

    @classmethod
    def get_template(cls):
        return 'mach/backend.html'

    @classmethod
    def get_form_class(cls):
        return MachBackendForm

    def get_sms_rate_limit(self):
        return self.config.max_sms_per_second * 60

    def send(self, msg, *args, **kwargs):
        config = self.config
        params = {
            'id': config.account_id,
            'pw': config.password,
            'snr': config.sender_id,
            'dnr': msg.phone_number,
        }
        try:
            text = msg.text.encode('iso-8859-1')
            params['msg'] = text
        except UnicodeEncodeError:
            params['msg'] = msg.text.encode('utf-16-be').encode('hex')
            params['encoding'] = 'ucs'
        url = '%s?%s' % (MACH_URL, urllib.urlencode(params))
        resp = urllib2.urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read()

        return resp
