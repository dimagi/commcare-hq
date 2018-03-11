from __future__ import absolute_import
from __future__ import unicode_literals
import pytz
import requests
from datetime import datetime
from corehq.apps.sms.models import SQLSMSBackend
from corehq.messaging.smsbackends.ivory_coast_mtn.exceptions import IvoryCoastMTNError
from corehq.messaging.smsbackends.ivory_coast_mtn.forms import IvoryCoastMTNBackendForm
from corehq.apps.sms.models import SMS
from corehq.apps.sms.util import strip_plus
from corehq.util.timezones.conversions import ServerTime
from lxml import etree


class IvoryCoastMTNBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'IVORY_COAST_MTN'

    @classmethod
    def get_generic_name(cls):
        return "Ivory Coast MTN"

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'customer_id',
            'username',
            'password',
            'sender_id',
        ]

    @classmethod
    def get_form_class(cls):
        return IvoryCoastMTNBackendForm

    @staticmethod
    def get_ivory_coast_timestamp():
        return ServerTime(datetime.utcnow()).user_time(pytz.timezone('Africa/Abidjan')).done()

    def get_params(self, msg_obj):
        config = self.config

        return {
            'customerID': config.customer_id,
            'userName': config.username,
            'userPassword': config.password,
            'originator': config.sender_id,
            # This is for a custom project and they only send messages in French
            'messageType': 'Latin',
            # This must be set to the date and time to send the message; it's a required field
            'defDate': self.get_ivory_coast_timestamp().strftime('%Y%m%d%H%M%S'),
            'blink': 'false',
            'flash': 'false',
            'private': 'false',
            'smsText': msg_obj.text.encode('utf-8'),
            'recipientPhone': msg_obj.phone_number,
        }

    @staticmethod
    def phone_number_is_valid(phone_number):
        phone_number = strip_plus(phone_number)
        # Phone number must be an Ivory Coast phone number
        # Also avoid processing numbers that are obviously too short
        return phone_number.startswith('225') and len(phone_number) > 3

    def send(self, msg_obj, *args, **kwargs):
        if not self.phone_number_is_valid(msg_obj.phone_number):
            msg_obj.set_system_error(SMS.ERROR_INVALID_DESTINATION_NUMBER)
            return

        response = requests.get(
            'http://smspro.mtn.ci/smspro/soap/messenger.asmx/HTTP_SendSms',
            params=self.get_params(msg_obj),
        )
        self.handle_response(msg_obj, response.status_code, response.text)

    @staticmethod
    def get_result_and_transaction_id(response_text):
        root_tag = etree.fromstring(response_text.encode('utf-8'))
        result_tag = root_tag.find('{http://pmmsoapmessenger.com/}Result')
        transaction_id_tag = root_tag.find('{http://pmmsoapmessenger.com/}TransactionID')

        return {
            'result': result_tag.text if result_tag is not None else None,
            'transaction_id': transaction_id_tag.text if transaction_id_tag is not None else None,
        }

    def handle_response(self, msg_obj, response_status_code, response_text):
        info = self.get_result_and_transaction_id(response_text)
        if info['transaction_id']:
            msg_obj.backend_message_id = info['transaction_id']

        if info['result'] != 'OK':
            raise IvoryCoastMTNError(
                "Received status %s and result '%s' for message %s, transaction %s" %
                (response_status_code, info['result'], msg_obj.couch_id, info['transaction_id'])
            )
