from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from dimagi.utils.logging import notify_exception

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, PhoneLoadBalancingMixin, SQLSMSBackend
from corehq.apps.sms.util import clean_phone_number
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

    def _convert_to_whatsapp(self, number):
        assert WHATSAPP_PREFIX not in number, "Attempted to re-convert a number already formatted for Whatsapp"
        return f"{WHATSAPP_PREFIX}{number}"

    def _convert_from_whatsapp(self, number):
        assert WHATSAPP_PREFIX in number, "Attempted to convert a number that is not formatted for Whatsapp"
        return number.replace(WHATSAPP_PREFIX, "")

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        if not orig_phone_number:
            raise Exception("Expected orig_phone_number to be passed for all "
                            "instances of PhoneLoadBalancingMixin")

        config = self.config
        client = Client(config.account_sid, config.auth_token)
        from_ = orig_phone_number
        to = msg.phone_number
        if toggles.WHATSAPP_MESSAGING.enabled(msg.domain) and not kwargs.get('skip_whatsapp', False):
            domain_obj = Domain.get_by_name(msg.domain)
            from_ = getattr(domain_obj, 'twilio_whatsapp_phone_number') or WHATSAPP_SANDBOX_PHONE_NUMBER
            from_ = self._convert_to_whatsapp(clean_phone_number(from_))
            to = self._convert_to_whatsapp(to)
        msg.system_phone_number = from_
        body = msg.text
        try:
            message = client.messages.create(
                body=body,
                to=to,
                from_=from_
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
