import re
from collections import namedtuple

from corehq.apps.sms.api import MessageMetadata, send_sms_with_backend
from corehq.apps.sms.models import SMS, MessagingEvent, SQLSMSBackend
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.turn.exceptions import WhatsAppTemplateStringException
from corehq.messaging.smsbackends.turn.forms import TurnBackendForm
from turn import TurnBusinessManagementClient, TurnClient
from turn.exceptions import WhatsAppContactNotFound

WA_TEMPLATE_STRING = "cc_wa_template"


class SQLTurnWhatsAppBackend(SQLSMSBackend):
    class Meta(object):
        proxy = True
        app_label = "sms"

    @classmethod
    def get_api_id(cls):
        return "TURN"

    @classmethod
    def get_generic_name(cls):
        return "Turn.io"

    @classmethod
    def get_available_extra_fields(cls):
        return [
            "template_namespace",
            "client_auth_token",
            "business_id",
            "business_auth_token",
            "fallback_backend_id",
        ]

    @classmethod
    def get_form_class(cls):
        return TurnBackendForm

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        config = self.config
        client = TurnClient(config.client_auth_token)
        to = clean_phone_number(msg.phone_number)
        try:
            wa_id = client.contacts.get_whatsapp_id(to)

            if is_whatsapp_template_message(msg.text):
                return self._send_template_message(client, wa_id, msg)
            else:
                return self._send_text_message(client, wa_id, msg)
        except WhatsAppContactNotFound:
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            if self.config.fallback_backend_id:
                self._send_fallback_message(msg)
            return False
        # TODO: Add other exceptions here

    def _send_template_message(self, client, wa_id, msg):
        try:
            parts = get_template_hsm_parts(msg.text)
        except WhatsAppTemplateStringException:
            msg.set_system_error(SMS.ERROR_MESSAGE_FORMAT_INVALID)

        if msg.invalid_survey_response:
            error_message = extract_error_message_from_template_string(msg.text)
            if error_message:
                client.messages.send_text(wa_id, error_message)

        return client.messages.send_templated_message(
            wa_id,
            self.config.template_namespace,
            parts.template_name,
            parts.lang_code,
            parts.params,
        )

    def _send_text_message(self, client, wa_id, msg):
        return client.messages.send_text(wa_id, msg.text)

    def _send_fallback_message(self, msg):
        logged_event = MessagingEvent.create_event_for_adhoc_sms(
            self.domain, recipient=msg.recipient
        )
        logged_subevent = logged_event.create_subevent_for_single_sms(
            recipient_doc_type=msg.recipient.doc_type, recipient_id=msg.recipient.get_id
        )
        metadata = MessageMetadata(
            messaging_subevent_id=logged_subevent.pk,
            custom_metadata={"fallback": "WhatsApp Contact Not Found"},
        )
        if send_sms_with_backend(
            self.domain, msg.phone_number, msg.text, self.config.fallback_backend_id, metadata
        ):
            logged_subevent.completed()
            logged_event.completed()
        else:
            logged_subevent.error(MessagingEvent.ERROR_INTERNAL_SERVER_ERROR)

    def get_all_templates(self):
        config = self.config
        client = TurnBusinessManagementClient(config.business_id, config.business_auth_token)
        return client.message_templates.get_message_templates()

    @classmethod
    def generate_template_string(cls, template):
        """From the template JSON returned by Turn, create the magic string for people to copy / paste
        """

        template_text = ""
        for component in template.get("components", []):
            if component.get("type") == "BODY":
                template_text = component.get("text", "")
                break
        num_params = template_text.count("{") // 2  # each parameter is bracketed by {{}}
        parameters = ",".join([f"{{var{i}}}" for i in range(1, num_params + 1)])
        return f"{WA_TEMPLATE_STRING}:{template['name']}:{template['language']}:{parameters}"

def is_whatsapp_template_message(message_text):
    return WA_TEMPLATE_STRING in message_text.lower()


def extract_error_message_from_template_string(message_text):
    """If message is labeled as "invalid_survey_response" then error message should be
    extracted from template string
    """
    return message_text.split(WA_TEMPLATE_STRING)[0]


def get_template_hsm_parts(message_text):
    """The magic string users enter looks like: cc_wa_template:template_name:lang_code:{var1}{var2}{var3}
    """
    HsmParts = namedtuple("hsm_parts", "template_name lang_code params")
    parts = message_text.split(":")

    try:
        params = re.findall("{(.+?)}+", parts[3])
    except IndexError:
        params = []

    try:
        return HsmParts(template_name=parts[1], lang_code=parts[2], params=params)
    except IndexError:
        raise WhatsAppTemplateStringException
