from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from dimagi.utils.logging import notify_exception

from corehq import toggles
from corehq.apps.sms.models import SMS, PhoneLoadBalancingMixin, SQLSMSBackend
from corehq.messaging.smsbackends.twilio.forms import TwilioBackendForm

# https://www.twilio.com/docs/api/errors/reference
ERROR_INVALID_TO_PHONE_NUMBER = 21211
ERROR_WHATSAPP_LIMITATION = 63032

WHATSAPP_PREFIX = "whatsapp:"


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
        if WHATSAPP_PREFIX not in number:
            number = f"{WHATSAPP_PREFIX}{number}"
        return number

    def _convert_from_whatsapp(self, number):
        if WHATSAPP_PREFIX in number:
            number = number.replace(WHATSAPP_PREFIX, "")
        return number

    def send(self, msg, orig_phone_number=None, *args, **kwargs):
        if not orig_phone_number:
            raise Exception("Expected orig_phone_number to be passed for all "
                            "instances of PhoneLoadBalancingMixin")

        if toggles.WHATSAPP_MESSAGING.enabled(msg.domain) and not kwargs.get('skip_whatsapp', False):
            orig_phone_number = self._convert_to_whatsapp(orig_phone_number)

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
            elif e.code == ERROR_WHATSAPP_LIMITATION:
                notify_exception(None, "Error with Twilio Whatsapp: %s" % str(e))
                orig_phone_number = self._convert_from_whatsapp(orig_phone_number)
                kwargs['skip_whatsapp'] = True
                self.send(msg, orig_phone_number, *args, **kwargs)
            else:
                raise

        msg.backend_message_id = message.sid
        msg.save()
