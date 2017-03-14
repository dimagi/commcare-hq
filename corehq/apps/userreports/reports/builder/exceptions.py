class SourceValidationError(Exception):
    def __init__(self, message, original_error=e):
