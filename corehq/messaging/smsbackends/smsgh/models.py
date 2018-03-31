from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import requests
from corehq.apps.sms.models import SMS, SQLSMSBackend
from corehq.messaging.smsbackends.smsgh.forms import SMSGHBackendForm


GHANA_COUNTRY_CODE = '233'
GHANA_PHONE_LENGTH = 12


class SMSGHException(Exception):
    pass


class SQLSMSGHBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'from_number',
            'client_id',
            'client_secret',
        ]

    @classmethod
    def get_url(cls):
        return 'https://api.smsgh.com/v3/messages/send'

    @classmethod
    def get_api_id(cls):
        return 'SMSGH'

    @classmethod
    def get_generic_name(cls):
        return "SMSGH"

    @classmethod
    def get_form_class(cls):
        return SMSGHBackendForm

    def response_is_error(self, response):
        return (int(response.status_code) // 100) in (4, 5)

    def get_additional_data(self, response):
        try:
            return response.json()
        except:
            return {}

    def handle_error(self, response, msg):
        data = self.get_additional_data(response)
        subcode = data.get('Status')
        if response.status_code == 502 and subcode == 4:
            # When this error happens, the gateway is saying that the
            # phone number is not a valid phone number.
            msg.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return
        elif response.status_code == 403 and subcode == 7:
            # When this error happens, it means the user has opted to not
            # receive SMS and has been added to a blacklist. If the user wants
            # to be removed from the blacklist, the user could either contact
            # their mobile operator or the gateway.
            msg.set_system_error(SMS.ERROR_PHONE_NUMBER_OPTED_OUT)
            return
        elif response.status_code == 404 and subcode is None:
            # This is a generic error returned by the gateway and should be
            # retried. Check for it here just so that it's documented, but
            # we'll just raise the exception below so that we are alerted
            # to the frequency of these errors and so that it will be retried
            # by the framework.
            pass
        raise SMSGHException("Error with the SMSGH backend. "
            "Response Code: %s, Subcode: %s. See 'Handling Errors' on "
            "https://developers.hubtel.com/documentations/sendmessage "
            "for details. " % (response.status_code, subcode))

    def handle_success(self, response, msg):
        data = self.get_additional_data(response)
        msg.backend_message_id = data.get('MessageId')

    def send(self, msg, *args, **kwargs):
        text = msg.text.encode('utf-8')

        config = self.config
        params = {
            'From': config.from_number,
            'To': msg.phone_number,
            'Content': text,
            'ClientId': config.client_id,
            'ClientSecret': config.client_secret,
        }
        response = requests.get(self.get_url(), params=params)

        if self.response_is_error(response):
            self.handle_error(response, msg)
        else:
            self.handle_success(response, msg)
