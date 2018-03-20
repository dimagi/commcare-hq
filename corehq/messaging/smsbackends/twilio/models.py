from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.models import SQLSMSBackend, PhoneLoadBalancingMixin, SMS
from corehq.messaging.smsbackends.twilio.forms import TwilioBackendForm
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from django.conf import settings

#https://www.twilio.com/docs/api/errors/reference
ERROR_INVALID_TO_PHONE_NUMBER = 21211


class SQLTwilioBackend(SQLSMSBackend, PhoneLoadBalancingMixin):

    class Meta(object):
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
        client = Client(config.account_sid, config.auth_token)
        to = msg.phone_number
        from_ = orig_phone_number
        msg.system_phone_number = from_
        body = msg.text
        try:
            message = client.messages.create(
                body=body,
                to=to,
                from_=from_
            )
        except TwilioRestException as e:
            if e.code == ERROR_INVALID_TO_PHONE_NUMBER:
                msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
                return
            else:
                raise

        msg.backend_message_id = message.sid
        msg.save()
