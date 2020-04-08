from corehq.apps.sms.models import SQLSMSBackend
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.turn.forms import TurnBackendForm
from turn import TurnClient
from turn.exceptions import WhatsAppContactNotFound


class SQLTurnWhatsAppBackend(SQLSMSBackend):

    class Meta(object):
        proxy = True
        app_label = 'sms'

    @classmethod
    def get_api_id(cls):
        return 'TURN'

    @classmethod
    def get_generic_name(cls):
        return "Turn.io"

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'username',
            'password',
            'auth_token',
        ]

    @classmethod
    def get_form_class(cls):
        return TurnBackendForm

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        config = self.config
        client = TurnClient(config.auth_token)
        to = clean_phone_number(msg.phone_number)

        try:
            wa_id = client.contacts.get_whatsapp_id(to)
        except WhatsAppContactNotFound:
            pass                # TODO: Fallback to SMS?

        try:
            message = client.messages.send_text(wa_id, msg.text)
        except:                 # TODO: Add message exceptions to package
            raise
