class EmailValidationException(Exception):
    def __init__(self, error_type, additional_text=None):
        self.error_type = error_type
        self.additional_text = additional_text


class FCMTokenValidationException(Exception):
    def __init__(self, error_type, additional_text=None):
        self.error_type = error_type
        self.additional_text = additional_text


class NoAvailableContent(Exception):
    pass


class RuleUpdateError(Exception):
    pass


class UnknownContentType(Exception):
    pass


class UnknownRecipientType(Exception):
    pass


class InvalidMonthlyScheduleConfiguration(Exception):
    pass


class ImmediateMessageEditAttempt(Exception):
    pass


class UnsupportedScheduleError(Exception):
    pass
