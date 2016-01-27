import requests
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.models import SMS, SQLSMSBackend
from corehq.apps.sms.util import strip_plus
from corehq.messaging.smsbackends.apposit.forms import AppositBackendForm
from dimagi.ext.couchdbkit import StringProperty


ETHIOPIA_COUNTRY_CODE = '251'


class AppositException(Exception):
    pass


class AppositBackend(SMSBackend):
    from_number = StringProperty()
    username = StringProperty()
    password = StringProperty()
    service_id = StringProperty()

    @classmethod
    def get_url(cls):
        return 'https://apps.apposit.com/tangio/messaging/http/send'

    @classmethod
    def get_api_id(cls):
        return 'APPOSIT'

    @classmethod
    def get_generic_name(cls):
        return 'Apposit'

    @classmethod
    def get_form_class(cls):
        return AppositBackendForm

    def response_is_error(self, response):
        return response.status_code != 200

    def get_additional_data(self, response):
        data = {}
        if isinstance(response.text, basestring) and '\r\n' in response.text:
            data['api_id'] = response.text.split('\r\n')[0]
        return data

    def is_ethiopia_number(self, msg):
        phone = strip_plus(msg.phone_number)
        return not phone.startswith(ETHIOPIA_COUNTRY_CODE)

    def handle_error(self, response, msg):
        data = self.get_additional_data(response)
        raise AppositException("Error with the Apposit backend. "
            "Response Code: %s, API Code: %s."
            % (response.status_code, data.get('api_code')))

    def send(self, msg, *args, **kwargs):
        if not self.is_ethiopia_number(msg):
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        params = {
            'username': self.username,
            'password': self.password,
            'serviceId': self.service_id,
            'content': msg.text.encode('utf-8'),
            'channel': 'SMS',
            'toAddress': msg.phone_number,
            'fromAddress': self.from_number,
        }
        response = requests.post(self.get_url(), data=params)

        if self.response_is_error(response):
            self.handle_error(response, msg)

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLAppositBackend


class SQLAppositBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'from_number',
            'username',
            'password',
            'service_id',
        ]

    @classmethod
    def get_url(cls):
        return 'https://apps.apposit.com/tangio/messaging/http/send'

    @classmethod
    def get_api_id(cls):
        return 'APPOSIT'

    @classmethod
    def get_generic_name(cls):
        return 'Apposit'

    @classmethod
    def get_form_class(cls):
        return AppositBackendForm

    def response_is_error(self, response):
        return response.status_code != 200

    def get_additional_data(self, response):
        data = {}
        if isinstance(response.text, basestring) and '\r\n' in response.text:
            data['api_id'] = response.text.split('\r\n')[0]
        return data

    def is_ethiopia_number(self, msg):
        phone = strip_plus(msg.phone_number)
        return phone.startswith(ETHIOPIA_COUNTRY_CODE)

    def handle_error(self, response, msg):
        data = self.get_additional_data(response)
        raise AppositException("Error with the Apposit backend. "
            "Response Code: %s, API Code: %s."
            % (response.status_code, data.get('api_code')))

    def send(self, msg, *args, **kwargs):
        if not self.is_ethiopia_number(msg):
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        config = self.config
        params = {
            'username': config.username,
            'password': config.password,
            'serviceId': config.service_id,
            'content': msg.text.encode('utf-8'),
            'channel': 'SMS',
            'toAddress': msg.phone_number,
            'fromAddress': config.from_number,
        }
        response = requests.post(self.get_url(), data=params)

        if self.response_is_error(response):
            self.handle_error(response, msg)
