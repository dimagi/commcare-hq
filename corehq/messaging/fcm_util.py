import logging
import os

from django.conf import settings
from firebase_admin import messaging, credentials, initialize_app

logger = logging.getLogger(__name__)

MAX_DEVICES_ALLOWED_MULTICAST = 500
HQ_FCM_UTIL = None


def is_fcm_available():
    if not settings.FCM_CREDS_PATH:
        return False
    return os.path.isfile(settings.FCM_CREDS_PATH)


class FCMUtilException(Exception):
    pass


class DevicesLimitExceeded(FCMUtilException):
    def __init__(self):
        super().__init__(f"Max devices allowed is {MAX_DEVICES_ALLOWED_MULTICAST}! Please execute in batches.")


class FCMUtil:
    def __init__(self, app_name, creds_path=settings.FCM_CREDS_PATH):
        creds = credentials.Certificate(creds_path)
        self.app = initialize_app(credential=creds, name=app_name)

    @staticmethod
    def _build_notification(title, body):
        return messaging.Notification(
            title=title,
            body=body,
        )

    def send_to_single_device(self, registration_token, title, body, data=None):
        """
        Sends message to a single device.
        https://firebase.google.com/docs/cloud-messaging/send-message#send-messages-to-specific-devices
        """
        message = messaging.Message(
            notification=self._build_notification(title, body),
            token=registration_token,
            data=data
        )
        response = messaging.send(message, app=self.app)
        # print(response)
        return response

    def send_to_multiple_devices(self, registration_tokens, title, body, data=None):
        """
        Sends message to multiple devices.
        https://firebase.google.com/docs/cloud-messaging/send-message#send-messages-to-multiple-devices
        """
        assert isinstance(registration_tokens, list)
        if len(registration_tokens) > MAX_DEVICES_ALLOWED_MULTICAST:
            raise DevicesLimitExceeded()
        message = messaging.MulticastMessage(
            notification=self._build_notification(title, body),
            tokens=registration_tokens,
            data=data
        )
        response = messaging.send_multicast(message, app=self.app)
        return response


if not is_fcm_available():
    logger.warning("Firebase Cloud Messaging is not available for this HQ environment!")
else:
    HQ_FCM_UTIL = FCMUtil(app_name='hq_fcm')
