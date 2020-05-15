from corehq.apps.sms.models import SQLSMSBackend, SMS
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.infobip.forms import InfobipBackendForm

WHATSAPP_PREFIX = "whatsapp:"
WHATSAPP_SANDBOX_PHONE_NUMBER = "14155238886"


class SQLInfobipBackend(SQLSMSBackend):

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
        config = self.config
        to = clean_phone_number(msg.phone_number)
        try:
            self._send_text_message(config, to, msg)
        except Exception:
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return False
        # TODO: Add other exceptions here

    def _send_text_message(self, config, to, msg):
        import http.client
        conn = http.client.HTTPSConnection("dmm5zv.api.infobip.com")

        payload = "{\"destinations\":[{\"to\":{\"phoneNumber\":\"%s\"}}],\"whatsApp\":{\"text\":\"%s\"}}" % (to, msg.text)
        headers = {
            'Authorization': 'App ' + str(config.auth_token),
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        return conn.request("POST", "/omni/1/advanced", payload, headers)


