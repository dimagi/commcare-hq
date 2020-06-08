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
        return "http://api.trumpia.com/http/v2/sendverificationsms"

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
        params = {
            "apikey": self.config.api_key,
            "country_code": 0,  # infer from mobile_number, which must start with '+'
            "mobile_number": msg.phone_number,
            "message": msg.text,
            "concat": "TRUE",
        }
        response = requests.get(
            self.get_url(),
            params=params,
            headers={"Accept": "application/json"},
            timeout=settings.SMS_GATEWAY_TIMEOUT,
        )
        self.handle_response(response, msg)

    def handle_response(self, response, msg):
        if response.status_code != 200:
            if response.status_code == 500:
                raise TrumpiaRetry("Gateway 500 error")
            msg.set_gateway_error(response.status_code)
            return
        data = response.json()
        if "requestID" in data:
            msg.backend_message_id = data["requestID"]
            data = self.get_message_details(data["requestID"])
            if is_success(data):
                return  # success
            if "statuscode" in data:
                message = f"status {data['statuscode']}: {data.get('message')}"
            else:
                message = repr(data)
        else:
            message = repr(data)
        msg.set_gateway_error(message)

    def get_message_details(self, request_id):
        """Get message status for the given SMS object

        Note: could register for a push notification to get a detailed
        message status report. Deferring that for now since none of our
        other gateways do that. We may want to do that if we frequently
        get a status code like MRCE4001 (request is being processed).

        :returns: Report dict, which is empty if the msg object had no
        backend message id.
        """
        response = requests.get(
            "http://api.trumpia.com/http/v2/checkresponse",
            params={"request_id": request_id},
            headers={"Accept": "application/json"},
        )
        return response.json()


def is_success(data):
    # 0: failure, 1: success
    return data.get("statuscode") == "1"
