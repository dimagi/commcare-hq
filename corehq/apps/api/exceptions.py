class UpdateUserException(Exception):
    """Raised when an error is encountered attempting to update a mobile user"""

    def __init__(self, message):
        self.message = message
