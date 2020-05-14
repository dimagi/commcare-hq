from corehq.apps.sms.models import PhoneLoadBalancingMixin, SQLSMSBackend
from corehq.messaging.smsbackends.infobip.forms import InfobipBackendForm

INVALID_TO_PHONE_NUMBER_ERROR_CODE = ""
WHATSAPP_LIMITATION_ERROR_CODE = ""

WHATSAPP_PREFIX = "whatsapp:"
WHATSAPP_SANDBOX_PHONE_NUMBER = "14155238886"


class SQLInfobipBackend(SQLSMSBackend, PhoneLoadBalancingMixin):

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
        return 'INFOBIP'

    @classmethod
    def get_generic_name(cls):
        return "Infobip"

    @classmethod
    def get_form_class(cls):
        return InfobipBackendForm

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
        pass
        # to be implemented
