import base64
import json
import requests
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.rest_tcl.exceptions import RestTCLError
from corehq.messaging.smsbackends.rest_tcl.forms import RestTCLBackendForm
from corehq.apps.sms.models import SMS
from corehq.apps.sms.util import strip_plus
from django.conf import settings


class RestTCLBackend(SQLSMSBackend):

    CONTENT_TYPE_PLAIN_MESSAGE = 'PM'
    CONTENT_TYPE_UNICODE = 'UC'

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'REST_TCL'

    @classmethod
    def get_generic_name(cls):
        return "RestTCL (through TCL)"

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'username',
            'password',
            'sender_id',
        ]

    @classmethod
    def get_form_class(cls):
        return RestTCLBackendForm

    def get_auth_key(self):
        # With Python 3, b64encode() needs to be passed `bytes`, and json.dumps()
        # needs to be passed `str`. So the return value here will be `str`.
        config = self.config
        username_and_password = '{}:{}'.format(config.username, config.password).encode('ascii')
        return base64.b64encode(username_and_password).decode('ascii')

    @staticmethod
    def get_text_and_content_type(msg_obj):
        # Since json.dumps() needs to be passed strings as `str` and not `bytes`,
        # we return the text as `str`.
        try:
            msg_obj.text.encode('ascii')
            return (msg_obj.text, RestTCLBackend.CONTENT_TYPE_PLAIN_MESSAGE)
        except UnicodeEncodeError:
            return (msg_obj.text, RestTCLBackend.CONTENT_TYPE_UNICODE)

    def get_json_payload(self, msg_obj):
        config = self.config
        text, content_type = self.get_text_and_content_type(msg_obj)

        # 'vp' is validity period, and we set it to the maximum value (1 day)
        return {
            'ver': '1.0',
            'key': self.get_auth_key(),
            'messages': [
                {
                    'dest': [strip_plus(msg_obj.phone_number)],
                    'send': config.sender_id,
                    'text': text,
                    'type': content_type,
                    'vp': '1440',
                },
            ],
        }

    @staticmethod
    def phone_number_is_valid(phone_number):
        phone_number = strip_plus(phone_number)
        # Only send to Indian phone numbers.
        # Also avoid processing numbers that are obviously too short.
        return phone_number.startswith('91') and len(phone_number) > 3

    def send(self, msg_obj, *args, **kwargs):
        if not self.phone_number_is_valid(msg_obj.phone_number):
            msg_obj.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        response = requests.post(
            'https://api.tatacommunications.com/mmx/v1/messaging/sms',
            data=json.dumps(self.get_json_payload(msg_obj)),
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        self.handle_response(msg_obj, response)

    @staticmethod
    def handle_response(msg_obj, response):
        if response.status_code != 200:
            raise RestTCLError("Received HTTP status code %s" % response.status_code)

        # If response.json() fails hard, that's ok, it means an invalid response
        # was returned. It will cause the exception to be notified and this message
        # will be retried.
        response_json = response.json()
        application_status_code = response_json.get('status', {}).get('code')

        if application_status_code != '200':
            raise RestTCLError("Received application status code %s" % application_status_code)

        # To avoid double-saving, no need to save. The framework saves the message later.
        msg_obj.backend_message_id = response_json.get('ackid')
