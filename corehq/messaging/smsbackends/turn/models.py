from collections import namedtuple

from corehq.apps.sms.models import SQLSMSBackend
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
            "client_auth_token",
            "business_id",
            "business_auth_token",
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
        except WhatsAppContactNotFound:
            pass  # TODO: Fallback to SMS?

        try:
            message = client.messages.send_text(wa_id, msg.text)
        except:  # TODO: Add message exceptions to package
            raise

    def get_all_templates(self):
        config = self.config
        client = TurnBusinessManagementClient(config.business_id, config.business_auth_token)
        return client.message_templates.get_message_templates()


def is_whatsapp_template_message(message_text):
    return message_text.lower().startswith(WA_TEMPLATE_STRING)


def get_template_hsm_parts(message_text):
    HsmParts = namedtuple("hsm_parts", "template_name lang_code variables")
    parts = message_text.split("~")[0].split(":")

    try:
        variables = [p.strip() for p in parts[3].split(",")]
    except IndexError:
        variables = []

    try:
        return HsmParts(template_name=parts[1], lang_code=parts[2], variables=variables,)
    except IndexError:
        raise WhatsAppTemplateStringException
