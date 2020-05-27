import boto3
from corehq.apps.sms.models import SQLSMSBackend
from corehq.apps.sms.util import clean_phone_number
from corehq.messaging.smsbackends.amazon_pinpoint.forms import PinpointBackendForm

MESSAGE_TYPE = "TRANSACTIONAL"


class SQLPinpointBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return [
            'reply_to_phone_number',
            'project_id',
            'region',
            'access_key',
            'secret_access_key'
        ]

    @classmethod
    def get_api_id(cls):
        return 'PINPOINT'

    @classmethod
    def get_generic_name(cls):
        return "Amazon Pinpoint"

    @classmethod
    def get_form_class(cls):
        return PinpointBackendForm

    def send(self, msg, *args, **kwargs):
        phone_number = clean_phone_number(msg.phone_number)
        text = msg.text.encode('utf-8')
        config = self.config
        client = boto3.client(
            'pinpoint',
            region_name=config.region,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_access_key
        )
        response = client.send_messages(
            ApplicationId=config.project_id,
            MessageRequest={
                'Addresses': {
                    phone_number: {
                        'ChannelType': 'SMS'
                    }
                },
                'MessageConfiguration': {
                    'SMSMessage': {
                        'Body': text,
                        'MessageType': MESSAGE_TYPE,
                        'OriginationNumber': config.reply_to_phone_number
                    }
                }
            }
        )
        return response
