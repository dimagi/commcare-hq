import json

from django.conf import settings

import requests

from corehq.apps.sms.models import SQLSMSBackend

from .forms import TrumpiaBackendForm


class TrumpiaRetry(Exception):
    pass


class TrumpiaBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return ['username', 'api_key']

    def get_url(self):
        return f'http://api.trumpia.com/rest/v1/{self.config.username}/sms'

    @classmethod
    def get_api_id(cls):
        return 'TRUMPIA'

    @classmethod
    def get_generic_name(cls):
        return "Trumpia"

    @classmethod
    def get_form_class(cls):
        return TrumpiaBackendForm

    def send(self, msg, *args, **kwargs):
        data = {
            "country_code": 0,  # inferred from mobile_number, which must start with '+'
            "mobile_number": msg.phone_number,
            "message": msg.text,
        }
        headers = {
            "X-Apikey": self.config.api_key,
            "Content-Type": "application/json",
        }
        response = requests.put(
            self.get_url(),
            data=json.dumps(data),
            headers=headers,
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )
        self.handle_response(response, msg)

    def handle_response(self, response, msg):
        if response.status_code == 200:
            # Could register for a push notification to get a detailed
            # message status report. Deferring that for now since none
            # of our other gateways do that. We may want to do that to
            # get more specific failure details. `backend_message_id`
            # can be used to retrieve the report if needed.
            data = response.json()
            msg.backend_message_id = data["request_id"]
        elif response.status_code == 500:
            raise TrumpiaRetry("Gateway 500 error")
        else:
            msg.set_gateway_error(response.status_code)
