import re
import requests
from corehq.apps.sms.forms import BackendForm
from corehq.apps.sms.models import SMS, SQLSMSBackend
from django.conf import settings


ERROR_NOT_WHITELISTED = re.compile(r"^error, +?\d+ is not whitelisted ")


class StarfishException(Exception):
    pass


class StarfishBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return []

    @classmethod
    def get_url(cls):
        return 'http://154.72.79.86/services/jsi/broadcast'

    @classmethod
    def get_api_id(cls):
        return 'STARFISH'

    @classmethod
    def get_generic_name(cls):
        return "Starfish"

    @classmethod
    def get_form_class(cls):
        return BackendForm

    def response_is_error(self, response):
        return (
            response.status_code != 200 or
            not response.text.startswith("success=")
        )

    def handle_error(self, response, msg):
        if response.status_code == 200:
            if response.text.startswith("invalid="):
                msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
                return
            if ERROR_NOT_WHITELISTED.match(response.text):
                msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
                return
        raise StarfishException(
            "Received HTTP response %s from starfish backend" % response.status_code
        )

    def send(self, msg, *args, **kwargs):
        payload = {
            "msisdn": msg.phone_number,
            "message": msg.text.encode('utf-8'),
        }
        response = requests.get(
            self.get_url(),
            params=payload,
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )

        if self.response_is_error(response):
            self.handle_error(response, msg)
