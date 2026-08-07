class RequestConnectionError(Exception):
    pass


class ReferralError(Exception):
    pass


class DataRegistryCaseUpdateError(Exception):
    pass


class PayloadNotFoundError(Exception):
    """Raised when the doc a payload is generated from is deleted or missing."""


class UnknownRepeater(Exception):
    """Exception raised when an Unknown Repeater type's instance is created.

    Attributes:
        repeater_type
    """

    def __init__(self, repeater_type):
        self.message = f"""{repeater_type} Repeater class not found"""
        super().__init__(self.message)

    def __str__(self):
        return self.message


class BulkActionMissingParameters(Exception):
    pass
