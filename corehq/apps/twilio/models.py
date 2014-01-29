import logging
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.twilio.forms import TwilioBackendForm
from couchdbkit.ext.django.schema import *
from twilio.rest import TwilioRestClient

class TwilioBackend(SMSBackend):
    account_sid = StringProperty()
    auth_token = StringProperty()
    phone_number = StringProperty()

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

    def send(self, msg, *args, **kwargs):
        client = TwilioRestClient(self.account_sid, self.auth_token)
        to = msg.phone_number
        from_ = clean_phone_number(self.phone_number)
        body = msg.text
        message = client.sms.messages.create(
            body=body,
            to=to,
            from_=from_
        )
        msg.backend_message_id = message.sid
        msg.save()

