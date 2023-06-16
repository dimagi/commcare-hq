import logging
import os

from django.conf import settings
from firebase_admin import messaging, credentials, initialize_app

logger = logging.getLogger(__name__)

MAX_DEVICES_ALLOWED_MULTICAST = 500
HQ_FCM_UTIL = None


class FCMUtilException(Exception):
    pass


class DevicesLimitExceeded(FCMUtilException):
    def __init__(self):
        super().__init__(f"Max devices allowed is {MAX_DEVICES_ALLOWED_MULTICAST}! Please execute in batches.")


class EmptyData(FCMUtilException):
    def __init__(self):
        super().__init__("One of the fields from 'title, body, data' is required!")


class FCMUtil:
    def __init__(self, app_name, fcm_creds=settings.FCM_CREDS):
        creds = credentials.Certificate(fcm_creds)
        self.app = initialize_app(credential=creds, name=app_name)

    @staticmethod
    def _build_notification(title, body):
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
            data=data
        )
        if title or body:
            message.notification = self._build_notification(title, body)
        response = messaging.send(message, app=self.app)
        return response

    def send_to_multiple_devices(self, registration_tokens, title='', body='', data=None):
        """
        Sends message to multiple devices.
        https://firebase.google.com/docs/cloud-messaging/send-message#send-messages-to-multiple-devices
        Pass only data to send notification of type 'Data Messages'.
        https://firebase.google.com/docs/cloud-messaging/concept-options
        """
        assert isinstance(registration_tokens, list)
        if len(registration_tokens) > MAX_DEVICES_ALLOWED_MULTICAST:
            raise DevicesLimitExceeded()
        self.check_for_empty_notification(title, body, data)
        message = messaging.MulticastMessage(
            tokens=registration_tokens,
            data=data
        )
        if title or body:
            message.notification = self._build_notification(title, body)
        response = messaging.send_multicast(message, app=self.app)
        return response


if settings.FCM_CREDS:
    HQ_FCM_UTIL = FCMUtil(app_name='hq_fcm')
