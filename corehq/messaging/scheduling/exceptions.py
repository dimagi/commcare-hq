

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
