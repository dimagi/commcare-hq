import requests
import json
from io import BytesIO
from django.core.files.uploadedfile import UploadedFile
from corehq.apps.sms.models import SQLSMSBackend, SMS
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.infobip.forms import InfobipBackendForm
from corehq.apps.smsbillables.exceptions import RetryBillableTaskException
from corehq.messaging.util import send_fallback_message
from corehq.messaging.whatsapputil import (
    WhatsAppTemplateStringException,
    is_whatsapp_template_message,
    get_template_hsm_parts, WA_TEMPLATE_STRING,
    extract_error_message_from_template_string,
    is_multimedia_message,
    get_multimedia_urls
)

INFOBIP_DOMAIN = "api.infobip.com"


class InfobipRetry(Exception):
    pass


class InfobipBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    using_api_to_get_fees = True

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
            if self.config.fallback_backend_id:
                send_fallback_message(self.domain, self.config.fallback_backend_id, msg)
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
        url = f'https://{config.personalized_subdomain}.{INFOBIP_DOMAIN}/omni/1/advanced'

        if is_whatsapp_template_message(msg.text):
            if msg.invalid_survey_response:
                error_message = extract_error_message_from_template_string(msg.text)
                if error_message:
                    payload['whatsApp'] = {'text': error_message}
                    requests.post(url, json=payload, headers=headers)

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
            if is_multimedia_message(msg):
                payload['whatsApp'] = {}
                image_url, audio_url, video_url = get_multimedia_urls(msg)
                if image_url:
                    payload['whatsApp']['imageUrl'] = image_url
                if audio_url:
                    payload['whatsApp']['audioUrl'] = audio_url
                if video_url:
                    payload['whatsApp']['videoUrl'] = video_url

                requests.post(url, json=payload, headers=headers)

            payload['whatsApp'] = {
                'text': msg.text
            }

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
        if response.status_code == 500:
            raise InfobipRetry("Gateway 500 error")
        if response.status_code != 200:
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

    def download_incoming_media(self, media_url):
        file_id = media_url.rsplit('/', 1)[-1]
        headers = {
            'Authorization': f'App {self.config.auth_token}',
            'Accept': 'application/json'
        }
        response = requests.get(media_url, headers=headers)
        uploaded_file = UploadedFile(
            BytesIO(response.content),
            file_id,
            content_type=response.headers.get('content-type')
        )
        return file_id, uploaded_file

    @classmethod
    def generate_template_string(cls, template):
        """From the template JSON returned by Infobip, create the magic string for people to copy / paste
        """

        template_text = template.get("body", "")
        num_params = template_text.count("{") // 2  # each parameter is bracketed by {{}}
        parameters = ",".join(f"{{var{i}}}" for i in range(1, num_params + 1))
        return f"{WA_TEMPLATE_STRING}:{template['name']}:{template['language']}:{parameters}"

    def get_message(self, backend_message_id):
        try:
            config = self.config
            api_channel = '/sms/1'
            api_suffix = '/reports'
            if config.scenario_key:
                api_channel = '/omni/1'

            headers = {
                'Authorization': f'App {config.auth_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            parameters = {
                'messageId': backend_message_id
            }
            messages = self._get_message_details(api_channel, api_suffix, config, headers, parameters)
            if not messages:
                api_suffix = '/logs'
                messages = self._get_message_details(api_channel, api_suffix, config, headers, parameters)
            return messages[0]
        except Exception as e:
            raise RetryBillableTaskException(str(e))

    def _get_message_details(self, api_channel, api_suffix, config, headers, parameters):
        url = f'https://{config.personalized_subdomain}.{INFOBIP_DOMAIN}{api_channel}{api_suffix}'
        response = requests.get(url, params=parameters, headers=headers)
        return response.json()['results']

    def get_provider_charges(self, backend_message_id):
        message = self.get_message(backend_message_id)
        segments = message['messageCount'] if 'messageCount' in message else message['smsCount']
        return message['status']['name'], message['price']['pricePerMessage'], int(segments)
