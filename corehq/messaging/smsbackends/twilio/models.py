import logging
from corehq.apps.sms.models import SQLSMSBackend, PhoneLoadBalancingMixin
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.twilio.forms import TwilioBackendForm
from dimagi.ext.couchdbkit import *
from twilio.rest import TwilioRestClient
from django.conf import settings


class SQLTwilioBackend(SQLSMSBackend, PhoneLoadBalancingMixin):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'account_sid',
            'auth_token',
        ]

    @classmethod
    def get_api_id(cls):
        return 'TWILIO'

    @classmethod
    def get_generic_name(cls):
        return "Twilio"

    @classmethod
    def get_form_class(cls):
        return TwilioBackendForm

    @classmethod
    def get_opt_in_keywords(cls):
        return ['START', 'YES']

    @classmethod
    def get_opt_out_keywords(cls):
        return ['STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT']

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        if not orig_phone_number:
            raise Exception("Expected orig_phone_number to be passed for all "
                            "instances of PhoneLoadBalancingMixin")

        config = self.config
        client = TwilioRestClient(config.account_sid, config.auth_token,
            timeout=settings.SMS_GATEWAY_TIMEOUT)
        to = msg.phone_number
        from_ = orig_phone_number
        body = msg.text
        message = client.messages.create(
            body=body,
            to=to,
            from_=from_
        )
        msg.system_phone_number = from_
        msg.backend_message_id = message.sid
        msg.save()
