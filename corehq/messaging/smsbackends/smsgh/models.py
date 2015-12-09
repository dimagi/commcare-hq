import requests
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.models import SMS, SQLSMSBackend
from corehq.apps.sms.util import strip_plus
from corehq.messaging.smsbackends.smsgh.forms import SMSGHBackendForm
from dimagi.ext.couchdbkit import StringProperty


GHANA_COUNTRY_CODE = '233'
GHANA_PHONE_LENGTH = 12


class SMSGHException(Exception):
    pass


class SMSGHBackend(SMSBackend):
    from_number = StringProperty()
    client_id = StringProperty()
    client_secret = StringProperty()

    @classmethod
    def get_url(cls):
        return 'https://api.smsgh.com/v3/messages/send'

    @classmethod
    def get_api_id(cls):
        return 'SMSGH'

    @classmethod
    def get_generic_name(cls):
        return 'SMSGH'

    @classmethod
    def get_form_class(cls):
        return SMSGHBackendForm

    def response_is_error(self, response):
        return (int(response.status_code) / 100) in (4, 5)

    def get_additional_data(self, response):
        try:
            return response.json()
        except:
            return {}

    def handle_error(self, response, msg):
        phone = strip_plus(msg.phone_number)
        if not (phone.startswith(GHANA_COUNTRY_CODE) and len(phone) == GHANA_PHONE_LENGTH):
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return
        data = self.get_additional_data(response)
        raise SMSGHException("Error with the SMSGH backend. "
            "Response Code: %s, Subcode: %s. See "
            "http://developers.smsgh.com/documentations/sendmessage#handlingerrors "
            "for details. " % (response.status_code, data.get('Status')))

    def handle_success(self, response, msg):
        data = self.get_additional_data(response)
        msg.backend_message_id = data.get('MessageId')

    def send(self, msg, *args, **kwargs):
        text = msg.text.encode('utf-8')

        params = {
            'From': self.from_number,
            'To': msg.phone_number,
            'Content': text,
            'ClientId': self.client_id,
            'ClientSecret': self.client_secret,
        }
        response = requests.get(self.get_url(), params=params)

        if self.response_is_error(response):
            self.handle_error(response, msg)
        else:
            self.handle_success(response, msg)

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLSMSGHBackend


class SQLSMSGHBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def _migration_get_couch_model_class(cls):
        return SMSGHBackend

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'from_number',
            'client_id',
            'client_secret',
        ]
