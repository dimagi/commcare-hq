from django.conf import settings
from django.utils.translation import gettext as _

from firebase_admin import credentials, initialize_app, messaging

from corehq.messaging.fcm.exceptions import (
    DevicesLimitExceeded,
    EmptyData,
    FCMNotSetup,
)

MAX_DEVICES_ALLOWED_MULTICAST = 500

if settings.FCM_CREDS:
    creds = credentials.Certificate(settings.FCM_CREDS)
    default_app = initialize_app(credential=creds, name='hq_fcm')


class FCMUtil:
    def __init__(self):
        if not settings.FCM_CREDS:
            raise FCMNotSetup()
        self.app = default_app

    @staticmethod
    def _build_notification(title, body):
        if title or body:
            return messaging.Notification(
                title=title,
                body=body,
            )

    @staticmethod
    def check_for_empty_notification(title, body, data):
        if not (title or body or data):
            raise EmptyData()

    def send_to_single_device(self, registration_token, title='', body='', data=None):
        """
        Sends message to a single device.
        https://firebase.google.com/docs/cloud-messaging/send-message#send-messages-to-specific-devices
        Pass only data to send notification of type 'Data Messages'.
        https://firebase.google.com/docs/cloud-messaging/concept-options
        """
        self.check_for_empty_notification(title, body, data)
        message = messaging.Message(
            token=registration_token,
            data=data,
            notification=self._build_notification(title, body)
        )
        response = messaging.send(message, app=self.app)
        return response

    def send_to_multiple_devices(self, registration_tokens, title='', body='', data=None):
        """
        Sends message to multiple devices.
        https://firebase.google.com/docs/cloud-messaging/send-message#send-messages-to-multiple-devices
        Pass only data to send notification of type 'Data Messages'.
        https://firebase.google.com/docs/cloud-messaging/concept-options
        This returns a batch response with format as 'Batch Response' available in
        """
        assert isinstance(registration_tokens, list)
        if len(registration_tokens) > MAX_DEVICES_ALLOWED_MULTICAST:
            raise DevicesLimitExceeded(message=_("Max devices allowed is {}! Please execute in batches.")
                                       .format(MAX_DEVICES_ALLOWED_MULTICAST))
        self.check_for_empty_notification(title, body, data)
        message = messaging.MulticastMessage(
            tokens=registration_tokens,
            data=data,
            notification=self._build_notification(title, body)
        )
        response = messaging.send_multicast(message, app=self.app)
        return response


def parse_multicast_batch_response(multicast_response, registration_tokens):
    """
    Parses the multicast batch response to a json format as below for easier usage.
    {
        'success_count': <integer>
        'failure_count': <integer>
        'success_responses':[
            {
                'token': <fcm_device_token>
                'message_id': <message_id>
            }
        ]
        'failure_responses':[
            {
                'token': <fcm_device_token>
                'exception':<fcm exception that occurred>
            }
        ]
    }
    'registration_tokens' parameter list have same order as the one sent to 'send_to_multiple_devices'
    """
    parsed_response = {
        'success_count': multicast_response.success_count,
        'failure_count': multicast_response.failure_count,
        'success_responses': [],
        'failure_responses': []
    }
    for idx, resp in enumerate(multicast_response.responses):
        if resp.success:
            parsed_response['success_responses'].append({
                'token': registration_tokens[idx],
                'message_id': resp.message_id
            })
        else:
            parsed_response['failure_responses'].append({
                'token': registration_tokens[idx],
                'exception': resp.exception
            })
    return parsed_response
