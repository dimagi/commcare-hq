from django.utils.translation import gettext as _


class FCMUtilException(Exception):
    pass


class DevicesLimitExceeded(FCMUtilException):
    def __init__(self, message):
        super().__init__(message)


class EmptyData(FCMUtilException):
    def __init__(self):
        super().__init__(_("One of the fields from 'title, body, data' is required!"))


class FCMNotSetup(FCMUtilException):
    def __init__(self):
        super().__init__(_("FCM is not setup on this environment!"))


class FCMTokenValidationException(Exception):
    def __init__(self, error_type, additional_text=None):
        self.error_type = error_type
        self.additional_text = additional_text
