class InvalidFormatException(Exception):

    def __init__(self, expected_type):
        self.expected_type = expected_type


class UnknownFieldException(Exception):
    pass
