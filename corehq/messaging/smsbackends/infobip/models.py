import requests
from corehq.apps.sms.models import SQLSMSBackend, SMS
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.infobip.forms import InfobipBackendForm

INFOBIP_HOST = "dmm5zv.api.infobip.com"


class SQLInfobipBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'account_sid',
            'auth_token',
            'scenario_key'
        ]

    @classmethod
    def get_api_id(cls):
        return 'INFOBIP'

    @classmethod
    def get_generic_name(cls):
        return "Infobip"

    @classmethod
    def get_form_class(cls):
        return InfobipBackendForm

    @classmethod
    def get_opt_in_keywords(cls):
        return ['START']

    @classmethod
    def get_pass_through_opt_in_keywords(cls):
        return ['YES']

    @classmethod
    def get_opt_out_keywords(cls):
        return ['STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT']

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        config = self.config
        to = clean_phone_number(msg.phone_number)
        try:
            self._send_text_message(config, to, msg)
            # TODO: Implement whatsapp template messages here
        except Exception:
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return False
        # TODO: Add other exceptions here

    def _send_text_message(self, config, to, msg):
        payload = {
            'destinations': [{'to': {'phoneNumber': to}}],
            'scenarioKey': config.scenario_key,
            'whatsApp': {'text': msg.text}
        }
        headers = {
            'Authorization': f'App {config.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        url = f'https://{INFOBIP_HOST}/omni/1/advanced'
        response = requests.post(url, json=payload, headers=headers)
        return response.content
