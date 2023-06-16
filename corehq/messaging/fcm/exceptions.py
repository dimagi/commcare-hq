class FCMUtilException(Exception):
    pass


class DevicesLimitExceeded(FCMUtilException):
    def __init__(self, message):
        super().__init__(message)


class EmptyData(FCMUtilException):
    def __init__(self):
        super().__init__("One of the fields from 'title, body, data' is required!")
