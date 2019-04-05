from __future__ import absolute_import
from __future__ import unicode_literals
import binascii
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
from django.conf import settings
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse
from corehq.apps.sms.models import SQLSMSBackend, SMS
from corehq.messaging.smsbackends.mach.forms import MachBackendForm
from corehq.util.python_compatibility import soft_assert_type_text
import six

MACH_URL = "http://smsgw.a2p.mme.syniverse.com/sms.php"


class SyniverseException(Exception):
    pass


class SQLMachBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

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
    def get_form_class(cls):
        return MachBackendForm

    def get_sms_rate_limit(self):
        return self.config.max_sms_per_second * 60

    def handle_error_response(self, msg, response):
        words = response.split()
        error_code = ''
        if len(words) > 1:
            error_code = words[1]

        config_error = {
            '52': SMS.ERROR_INVALID_DESTINATION_NUMBER,
            '59': SMS.ERROR_MESSAGE_TOO_LONG,
        }.get(error_code)

        if config_error:
            msg.set_system_error(config_error)
            return

        raise SyniverseException(
            "Received error code %s while sending SMS from Syniverse backend "
            "%s, see documentation for details." % (error_code, self.pk)
        )

    def handle_response(self, msg, response):
        if not isinstance(response, six.string_types):
            raise SyniverseException(
                "Unrecognized response received from Syniverse "
                "backend %s" % self.pk
            )
        soft_assert_type_text(response)

        response = response.strip().upper()
        if response.startswith('+OK'):
            return
        elif response.startswith('-ERR'):
            self.handle_error_response(msg, response)
        else:
            raise SyniverseException(
                "Unrecognized response received from Syniverse "
                "backend %s" % self.pk
            )

    def send(self, msg, *args, **kwargs):
        config = self.config
        params = {
            'id': config.account_id,
            'pw': config.password,
            'snr': config.sender_id,
            'dnr': msg.phone_number,
            'split': '10',
        }
        try:
            text = msg.text.encode('iso-8859-1')
            params['msg'] = text
        except UnicodeEncodeError:
            params['msg'] = binascii.hexlify(msg.text.encode('utf-16-be'))
            params['encoding'] = 'ucs'
        url = '%s?%s' % (MACH_URL, six.moves.urllib.parse.urlencode(params))
        resp = six.moves.urllib.request.urlopen(url, timeout=settings.SMS_GATEWAY_TIMEOUT).read().decode('utf-8')
        self.handle_response(msg, resp)
        return resp
