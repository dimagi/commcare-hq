from typing import Optional

from twilio.base import values
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from dimagi.utils.logging import notify_exception
from django.utils.decorators import classproperty

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, PhoneLoadBalancingMixin, SQLSMSBackend
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.smsbillables.exceptions import RetryBillableTaskException
from corehq.messaging.smsbackends.twilio.forms import TwilioBackendForm

# https://www.twilio.com/docs/api/errors/reference
INVALID_TO_PHONE_NUMBER_ERROR_CODE = 21211
WHATSAPP_LIMITATION_ERROR_CODE = 63032

WHATSAPP_PREFIX = "whatsapp:"
WHATSAPP_SANDBOX_PHONE_NUMBER = "14155238886"


class SQLTwilioBackend(SQLSMSBackend, PhoneLoadBalancingMixin):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    using_api_to_get_fees = True

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
        return ['START']

    @classmethod
    def get_pass_through_opt_in_keywords(cls):
        return ['YES']

    @classmethod
    def get_opt_out_keywords(cls):
        return ['STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT']

    @classmethod
    def convert_to_whatsapp(cls, number):
        if number.startswith(WHATSAPP_PREFIX):
            return number
        return f"{WHATSAPP_PREFIX}{number}"

    @classmethod
    def convert_from_whatsapp(cls, number):
        return number.replace(WHATSAPP_PREFIX, "")

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        if not orig_phone_number:
            raise Exception("Expected orig_phone_number to be passed for all "
                            "instances of PhoneLoadBalancingMixin")

        config = self.config
        client = Client(config.account_sid, config.auth_token)
        to = msg.phone_number
        msg.system_phone_number = orig_phone_number
        if toggles.WHATSAPP_MESSAGING.enabled(msg.domain) and not kwargs.get('skip_whatsapp', False):
            domain_obj = Domain.get_by_name(msg.domain)
            from_ = getattr(domain_obj, 'twilio_whatsapp_phone_number') or WHATSAPP_SANDBOX_PHONE_NUMBER
            from_ = clean_phone_number(from_)
            from_ = self.convert_to_whatsapp(from_)
            to = self.convert_to_whatsapp(to)
            messaging_service_sid = None
        else:
            from_, messaging_service_sid = self.from_or_messaging_service_sid(orig_phone_number)
        body = msg.text
        try:
            message = client.messages.create(
                body=body,
                to=to,
                from_=from_ or values.unset,
                messaging_service_sid=messaging_service_sid or values.unset,
            )
        except TwilioRestException as e:
            if e.code == INVALID_TO_PHONE_NUMBER_ERROR_CODE:
                msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
                return
            elif e.code == WHATSAPP_LIMITATION_ERROR_CODE:
                notify_exception(None, f"Error with Twilio Whatsapp: {e}")
                kwargs['skip_whatsapp'] = True
                self.send(msg, orig_phone_number, *args, **kwargs)
            else:
                raise

        msg.backend_message_id = message.sid
        msg.save()

    def from_or_messaging_service_sid(self, phone_number: str) -> (Optional[str], Optional[str]):
        if self.phone_number_is_messaging_service_sid(phone_number):
            return None, phone_number
        else:
            return phone_number, None

    @staticmethod
    def phone_number_is_messaging_service_sid(phone_number):
        return phone_number[:2] == 'MG'

    def _get_twilio_client(self):
        config = self.config
        return Client(config.account_sid, config.auth_token)

    def get_message(self, backend_message_id):
        try:
            return self._get_twilio_client().messages.get(backend_message_id).fetch()
        except TwilioRestException as e:
            raise RetryBillableTaskException(str(e))

    def get_provider_charges(self, backend_message_id):
        message = self.get_message(backend_message_id)
        return message.status, message.price, int(message.num_segments)
