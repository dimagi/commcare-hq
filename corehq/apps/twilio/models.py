import logging
from corehq.apps.sms.mixin import SMSBackend, SMSLoadBalancingMixin
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.twilio.forms import TwilioBackendForm
from couchdbkit.ext.django.schema import *
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
    def get_template(cls):
        return "twilio/backend.html"

    @classmethod
    def get_form_class(cls):
        return TwilioBackendForm

    def get_load_balancing_interval(self):
        # Twilio automatically rate limits at 1 sms/sec, but we'll also
        # balance the sms load evenly between the phone numbers used by
        # this backend over the last 60 seconds.
        return 60

    @property
    def phone_numbers(self):
        """
        Prior to introduction load balancing, the Twilio backend only had
        one phone number, so need to handle old Twilio backends which don't
        have the _phone_numbers property set.
        """
        if self.x_phone_numbers:
            return self.x_phone_numbers
        else:
            return [self.phone_number]

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

