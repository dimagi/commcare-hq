from collections import namedtuple

from yowsup.demos.sendclient import YowsupSendStack
from yowsup.layers import YowLayerEvent
from yowsup.layers.auth import AuthError
from yowsup.layers.network import YowNetworkLayer

from corehq.apps.sms.models import SQLSMSBackend
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.whatsapp.forms import WhatsAppBackendForm
from dimagi.utils import logging


YowsupMessage = namedtuple('YowsupMessage', 'phone body')


class SQLWhatsAppBackend(SQLSMSBackend):

    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'phone_number',
            'password',
        ]

    @classmethod
    def get_api_id(cls):
        return 'WHATSAPP'

    @classmethod
    def get_generic_name(cls):
        return "WhatsApp"

    @classmethod
    def get_form_class(cls):
        return WhatsAppBackendForm

    def get_credentials(self):
        config = self.config
        return (config.phone_number, config.password)

    def send(self, msg, *args, **kwargs):
        phone_number = clean_phone_number(msg.phone_number)
        messages = [YowsupMessage(phone_number, msg.text)]  # msg.text is expected to be Unicode

        stack = YowsupSendStack(self.get_credentials(), messages, encryptionEnabled=True)
        # stack.start()  # Reimplemented below, but notify on auth failure instead of printing it
        stack.stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))
        try:
            stack.stack.loop()  # TODO: discrete=5, count=X ?
        except AuthError as err:
            domain = ' for domain "{}"'.format(self.domain) if self.domain else ''
            logging.notify_error('WhatsApp authentication failure{domain}: {err}'.format(domain=domain, err=err))
        except KeyboardInterrupt:
            # Raised when messages sent and acks received
            pass
