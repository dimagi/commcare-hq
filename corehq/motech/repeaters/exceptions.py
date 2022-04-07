class RequestConnectionError(Exception):
    pass


class ReferralError(Exception):
    pass


class DataRegistryCaseUpdateError(Exception):
    pass


class UnknownRepeater(Exception):
    """Exception raised when an Unknown Repeater type's instance is created.

    Attributes:
        repeater_type
    """

    def __init__(self, repeater_type):
        self.message = f"""{repeater_type} Repeater class not found.
                Please ensure that you have added Repeater class info in
                1) REPEATER_CLASSES in settings.py
                2) REPEATER_CLASS_MAP in corehq.motech.const"""
        super().__init__(self.message)

    def __str__(self):
        return self.message
