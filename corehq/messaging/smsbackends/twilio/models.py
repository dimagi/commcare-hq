import logging
from corehq.apps.sms.mixin import SMSBackend, SMSLoadBalancingMixin
from corehq.apps.sms.models import SQLSMSBackend, PhoneLoadBalancingMixin
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.twilio.forms import TwilioBackendForm
from dimagi.ext.couchdbkit import *
from twilio.rest import TwilioRestClient
from django.conf import settings


class TwilioBackend(SMSBackend, SMSLoadBalancingMixin):
    account_sid = StringProperty()
    auth_token = StringProperty()

    @classmethod
    def get_api_id(cls):
        return "TWILIO"

    @classmethod
    def get_generic_name(cls):
        return "Twilio"

    @classmethod
    def get_form_class(cls):
        return TwilioBackendForm

    @classmethod
    def get_opt_in_keywords(cls):
        return ["START", "YES"]

    @classmethod
    def get_opt_out_keywords(cls):
        return ["STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]

    def get_load_balancing_interval(self):
        # Twilio automatically rate limits at 1 sms/sec, but we'll also
        # balance the sms load evenly between the phone numbers used by
        # this backend over the last 60 seconds.
        return 60

    @property
    def phone_numbers(self):
        """
        Prior to introducing load balancing, the Twilio backend only had
        one phone number, so need to handle old Twilio backends which don't
        have the x_phone_numbers property set.
        """
        if self.x_phone_numbers:
            return self.x_phone_numbers
        else:
            return [self.phone_number] if hasattr(self, 'phone_number') else []

    def send(self, msg, *args, **kwargs):
        orig_phone_number = kwargs.get("orig_phone_number")
        client = TwilioRestClient(self.account_sid, self.auth_token,
            timeout=settings.SMS_GATEWAY_TIMEOUT)
        to = msg.phone_number
        from_ = orig_phone_number or self.phone_numbers[0]
        body = msg.text
        message = client.messages.create(
            body=body,
            to=to,
            from_=from_
        )
        msg.system_phone_number = from_
        msg.backend_message_id = message.sid
        msg.save()

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLTwilioBackend


class SQLTwilioBackend(SQLSMSBackend, PhoneLoadBalancingMixin):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def _migration_get_couch_model_class(cls):
        return TwilioBackend

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
