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
        if response.status_code != 200:
            if response.status_code == 500:
                raise TrumpiaRetry("Gateway 500 error")
            msg.set_gateway_error(response.status_code)
            return
        data = response.json()
        if is_success(data):
            # Could register for a push notification to get a detailed
            # message status report. Deferring that for now since none
            # of our other gateways do that. We may want to do that to
            # get more specific failure details. `backend_message_id`
            # can be used to retrieve the report if needed.
            msg.backend_message_id = data["request_id"]
            return
        error = data.get("status_code")
        if not error:
            error = "blocked" if "blocked_mobile" in data else response.text
        elif error[-6:] in RETRY_CODES:
            raise TrumpiaRetry(f"Gateway error: {error}")
        msg.set_gateway_error(error)

    def get_message_details(self, sms):
        """Get message status for the given SMS object

        Useful for troubleshooting message failures in a shell.
        """
        headers = {
            "X-Apikey": self.config.api_key,
            "Content-Type": "application/json",
        }
        url = self.get_url()
        assert url.endswith("/sms")
        url = f"{url[:-4]}/report/{sms.backend_message_id}"
        response = requests.get(url, headers=headers)
        return response.json()


def is_success(data):
    return (
        "request_id" in data
        and data.get("status", "sent") == "sent"
        and data.get("status_code", "CE0000")[-6:] in SUCCESS_CODES
    )


# https://classic.trumpia.com/api/docs/rest/status-code/common.php
# https://classic.trumpia.com/api/docs/rest/status-code/direct-sms.php
SUCCESS_CODES = {
    "CE0000",  # success
    "CE4001",  # pending - interpret as success (see comment on success above)
}
RETRY_CODES = {
    "CE0301",  # The request failed due to a temporary issue. Please retry in a few moments.
    "CE0302",  # API Call is temporarily disabled due to an internal issue.
}
