import requests
from corehq.apps.sms.mixin import SMSBackend
from corehq.messaging.smsbackends.smsgh.forms import SMSGHBackendForm
from dimagi.ext.couchdbkit import StringProperty


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

    def handle_error(self, response):
        data = self.get_additional_data(response)
        raise SMSGHException("Error with the SMSGH backend. "
            "Response Code: %s, Subcode: %s. See "
            "http://developers.smsgh.com/documentations/sendmessage#handlingerrors "
            "for details. " % (response.status_code, data.get('Status')))

    def handle_success(self, response, msg):
        data = self.get_additional_data(response)
        msg.backend_message_id = data.get('MessageId')

    def send_sms(self, msg, *args, **kwargs):
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
            self.handle_error(response)
        else:
            self.handle_success(response, msg)
