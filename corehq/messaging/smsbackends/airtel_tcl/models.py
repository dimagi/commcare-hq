import json
import pytz
import requests
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.airtel_tcl.exceptions import AirtelTCLError, InvalidDestinationNumber
from corehq.messaging.smsbackends.airtel_tcl.forms import AirtelTCLBackendForm
from corehq.apps.sms.models import SMS
from corehq.apps.sms.util import strip_plus
from corehq.util.timezones.conversions import ServerTime
from datetime import datetime
from django.conf import settings


class AirtelTCLBackend(SQLSMSBackend):

    LANG_ID_DECIMAL_NCR = '2'

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'AIRTEL_TCL'

    @classmethod
    def get_generic_name(cls):
        return "Airtel (through TCL)"

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'host_and_port',
            'user_name',
            # Password isn't requested by the API, presumably because the service is whitelisted.
            # But we'll store it on the backend so we can keep track of it with everything else.
            'password',
            'sender_id',
            'circle_name',
            'campaign_name',
        ]

    @classmethod
    def get_form_class(cls):
        return AirtelTCLBackendForm

    @staticmethod
    def unicode_to_decimal_ncr(text):
        """
        Converts the message to Decimal NCR format.
        This is different from HTML escaping. For this
        we need each character to be represented by
        its character code, even if it's an ASCII character
        like a space.
        """
        return ''.join(['&#%s;' % ord(c) for c in text])

    @staticmethod
    def get_text_and_lang_id(msg_obj):
        try:
            msg_obj.text.encode('ascii')
            return (msg_obj.text, None)
        except UnicodeEncodeError:
            return (AirtelTCLBackend.unicode_to_decimal_ncr(msg_obj.text), AirtelTCLBackend.LANG_ID_DECIMAL_NCR)

    @staticmethod
    def get_timestamp():
        return ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done()

    @staticmethod
    def get_formatted_timestamp(timestamp):
        return timestamp.strftime('%d%m%Y%H%M%S')

    def get_json_payload(self, msg_obj):
        config = self.config
        text, lang_id = self.get_text_and_lang_id(msg_obj)
        msg_info = {
            'MSISDN': self.get_phone_number(msg_obj.phone_number),
            'OA': config.sender_id,
            'CIRCLE_NAME': config.circle_name,
            'CAMPAIGN_NAME': config.campaign_name,
            'MESSAGE': text,
            'USER_NAME': config.user_name,
            'CHANNEL': 'SMS',
        }

        if lang_id:
            msg_info['LANG_ID'] = lang_id

        return {
            'timeStamp': self.get_formatted_timestamp(self.get_timestamp()),
            # The keyword param is listed as mandatory but I was told it can be anything
            'keyword': 'ICDS',
            'dataSet': [msg_info],
        }

    def get_url(self):
        return 'https://%s/BULK_API/InstantJsonPush' % self.config.host_and_port

    @staticmethod
    def get_phone_number(phone_number):
        """
        Only send to Indian phone numbers. Also remove the country code before
        making the request.
        """
        phone_number = strip_plus(phone_number)
        if phone_number.startswith('91') and len(phone_number) > 2:
            return phone_number[2:]

        raise InvalidDestinationNumber()

    def send(self, msg_obj, *args, **kwargs):
        try:
            payload = self.get_json_payload(msg_obj)
        except InvalidDestinationNumber:
            msg_obj.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        response = requests.post(
            self.get_url(),
            data=json.dumps(payload),
            timeout=settings.SMS_GATEWAY_TIMEOUT,
            verify=False,
        )

        self.handle_response(response.status_code, response.text)

    @staticmethod
    def handle_response(response_status_code, response_text):
        if response_status_code != 200:
            raise AirtelTCLError("Received HTTP status code %s" % response_status_code)

        if response_text.strip() != 'true':
            raise AirtelTCLError("Unexpected response received from gateway")
