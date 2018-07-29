from __future__ import absolute_import
from __future__ import unicode_literals
from six.moves.urllib.parse import urlencode
from six.moves.urllib.request import urlopen

from crispy_forms import layout as crispy
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from corehq.apps.sms.models import SQLSMSBackend, SMS
from corehq.apps.sms.forms import BackendForm
from corehq.apps.sms.util import strip_plus
from dimagi.utils.django.fields import TrimmedCharField
from dimagi.utils.logging import notify_exception

ERR_INVALID_DESTINATION = '-410'

INDIA_COUNTRY_CODE = '91'

ERROR_CODES = {
    "-2": "Invalid credentials",
    "-3": "Empty mobile number",
    "-4": "Empty message",
    "-5": "HTTPS disabled",
    "-6": "HTTP disabled",
    "-13": "Internal Error",
    "-201": "Email Delivery Disabled",
    "-401": "Invalid Scheduled Time",
    "-404": "Invalid MsgType",
    "-406": "Invalid Port",
    "-407": "Invalid Expiry minutes",
    "-408": "Invalid Customer Reference Id",
    "-409": "Invalid Bill Reference Id",
    ERR_INVALID_DESTINATION: "Invalid Destination Address",
    "-432": "Invalid Bill Reference Id Length",
    "-433": "Invalid Customer Reference Id Length",
}

RETRY_ERROR_CODES = {"-13"}


class ICDSException(Exception):
    pass


class ICDSBackendForm(BackendForm):
    username = TrimmedCharField(
        label=_('Username'),
    )
    pin = TrimmedCharField(
        label=_('PIN'),
    )
    sender_id = TrimmedCharField(
        label=_('Sender ID'),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("ICDS Settings"),
            'username',
            'pin',
            'sender_id',
        )


class SQLICDSBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'username',
            'pin',
            'sender_id',
        ]

    @classmethod
    def get_api_id(cls):
        return 'ICDS'

    @classmethod
    def get_generic_name(cls):
        return "ICDS"

    @classmethod
    def get_form_class(cls):
        return ICDSBackendForm

    def destination_number_is_valid(self, phone_number):
        """
        phone_number is not expected to contain the leading + for this validation to work.
        """
        return phone_number.startswith(INDIA_COUNTRY_CODE) and phone_number != INDIA_COUNTRY_CODE

    def get_response_code(self, response):
        api_code_string = "~code=API"
        begin_response = response.find(api_code_string)
        if begin_response == -1:
            return None
        begin_response += len(api_code_string)
        end_response = response.find('&', begin_response)
        if end_response == -1:
            return None
        return response[begin_response:end_response].strip()

    def handle_error(self, response_code, msg):
        exception_message = "Error with ICDS backend. HTTP response code: %s, %s" % (
            response_code, ERROR_CODES.get(response_code, 'Unknown Error')
        )
        if response_code == ERR_INVALID_DESTINATION:
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return
        if response_code in RETRY_ERROR_CODES or response_code not in ERROR_CODES:
            raise ICDSException(exception_message)
        msg.set_system_error(SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
        notify_exception(None, exception_message)

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        config = self.config
        phone_number = strip_plus(msg.phone_number)

        if not self.destination_number_is_valid(phone_number):
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        try:
            text = msg.text.encode("iso-8859-1")
            msg_type = "PM"
        except UnicodeEncodeError:
            text = msg.text.encode("utf_16_be").encode('hex').upper()
            msg_type = "UC"
        params = {
            "username": config.username,
            "pin": config.pin,
            "mnumber": phone_number,
            "message": text,
            "signature": config.sender_id,
            "msgType": msg_type,
            "splitAlgm": "concat",
        }
        url_params = urlencode(params)
        url = 'https://smsgw.sms.gov.in/failsafe/HttpLink'
        response = urlopen("%s?%s" % (url, url_params),
                           timeout=settings.SMS_GATEWAY_TIMEOUT).read()

        response_code = self.get_response_code(response)
        if response_code != '000':
            self.handle_error(response_code, msg)
