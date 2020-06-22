import requests
import json
from corehq.apps.sms.models import SQLSMSBackend, SMS
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.infobip.forms import InfobipBackendForm
from corehq.messaging.whatsapputil import (
    WhatsAppTemplateStringException,
    is_whatsapp_template_message,
    get_template_hsm_parts, WA_TEMPLATE_STRING,
    extract_error_message_from_template_string
)

INFOBIP_DOMAIN = "api.infobip.com"


class InfobipRetry(Exception):
    pass


class InfobipBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'reply_to_phone_number',
            'account_sid',
            'auth_token',
            'personalized_subdomain',
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
        headers = {
            'Authorization': f'App {config.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        try:
            if config.scenario_key:
                self._send_omni_failover_message(config, to, msg, headers)
            else:
                self._send_sms(config, to, msg, headers)
        except Exception:
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return False

    def _send_omni_failover_message(self, config, to, msg, headers):
        payload = {
            'destinations': [{'to': {'phoneNumber': to}}],
            'scenarioKey': config.scenario_key,
            'viber': {'text': msg.text},
            'line': {'text': msg.text},
            'voice': {'text': msg.text},
            'sms': {'text': msg.text}
        }
        if is_whatsapp_template_message(msg.text):
            try:
                parts = get_template_hsm_parts(msg.text)
            except WhatsAppTemplateStringException:
                msg.set_system_error(SMS.ERROR_MESSAGE_FORMAT_INVALID)
            payload['whatsApp'] = {
                'templateName': parts.template_name,
                'language': parts.lang_code,
                'templateData': parts.params
            }
        else:
            payload['whatsApp'] = {'text': msg.text}

        url = f'https://{config.personalized_subdomain}.{INFOBIP_DOMAIN}/omni/1/advanced'
        response = requests.post(url, json=payload, headers=headers)
        self.handle_response(response, msg)

    def _send_sms(self, config, to, msg, headers):
        payload = {
            'messages': [{
                'from': config.reply_to_phone_number,
                'destinations': [{'to': to}],
                'text': msg.text
            }]
        }
        url = f'https://{config.personalized_subdomain}.{INFOBIP_DOMAIN}/sms/2/text/advanced'
        response = requests.post(url, json=payload, headers=headers)
        self.handle_response(response, msg)

    def handle_response(self, response, msg):
        if response.status_code != 200:
            if response.status_code == 500:
                raise InfobipRetry("Gateway 500 error")
            msg.set_gateway_error(response.status_code)
            return
        data = json.loads(response.content)
        if "messages" in data:
            msg.backend_message_id = data["messages"][0]["messageId"]
        else:
            message = repr(data)
            msg.set_gateway_error(message)

    def get_all_templates(self):
        headers = {
            'Authorization': f'App {self.config.auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        url = f'https://{self.config.personalized_subdomain}.{INFOBIP_DOMAIN}' \
            f'/whatsapp/1/senders/{self.config.reply_to_phone_number}/templates'
        response = requests.get(url, headers=headers)
        return json.loads(response.content).get('templates')

    @classmethod
    def generate_template_string(cls, template):
        """From the template JSON returned by Infobip, create the magic string for people to copy / paste
        """

        template_text = template.get("body", "")
        num_params = template_text.count("{") // 2  # each parameter is bracketed by {{}}
        parameters = ",".join(f"{{var{i}}}" for i in range(1, num_params + 1))
        return f"{WA_TEMPLATE_STRING}:{template['name']}:{template['language']}:{parameters}"
