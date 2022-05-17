class InvalidFieldException(Exception):

    def __init__(self, field):
        self.field = field


class InvalidFormatException(Exception):

    def __init__(self, field, expected_type):
        self.field = field
        self.expected_type = expected_type


class UpdateConflictException(Exception):

    def __init__(self, message):
        self.message = message
