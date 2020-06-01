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
        response = requests.put(
            self.get_url(),
            data=json.dumps(data),
            headers=self.http_headers,
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
        if "request_id" in data:
            msg.backend_message_id = data["request_id"]
            if data.get("status_code", "")[-6:] not in SUCCESS_CODES:
                data = self.get_message_details(msg)
            if is_success(data):
                return
        error = data.get("status_code")
        if not error:
            error = "blocked" if "blocked_mobile" in data else response.text
        elif error[-6:] in RETRY_CODES:
            raise TrumpiaRetry(f"Gateway error: {error}")
        msg.set_gateway_error(error)

    def get_message_details(self, msg):
        """Get message status for the given SMS object

        Note: could register for a push notification to get a detailed
        message status report. Deferring that for now since none of our
        other gateways do that. We may want to do that if we frequently
        get a status code like MRCE4001 (request is being processed).

        :returns: Report dict, which is empty if the msg object had no
        backend message id.
        """
        if not msg.backend_message_id:
            return {}
        url = self.get_url()
        assert url.endswith("/sms")
        url = f"{url[:-4]}/report/{msg.backend_message_id}"
        response = requests.get(url, headers=self.http_headers)
        return response.json()

    @property
    def http_headers(self):
        return {
            "X-Apikey": self.config.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


def is_success(data):
    return (
        data.get("status") == "sent"
        or data.get("status_code", "")[-6:] in SUCCESS_CODES
    )


# https://classic.trumpia.com/api/docs/rest/status-code/common.php
# https://classic.trumpia.com/api/docs/rest/status-code/direct-sms.php
SUCCESS_CODES = {
    "CE0000",  # success
    "CE4001",  # pending - interpret as success (see get_message_details note)
}
RETRY_CODES = {
    "CE0301",  # The request failed due to a temporary issue. Please retry in a few moments.
    "CE0302",  # API Call is temporarily disabled due to an internal issue.
}
