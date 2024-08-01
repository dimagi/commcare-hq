class AppExecutionError(Exception):
    pass


class FormplayerException(Exception):
    pass


class ExpectationFailed(Exception):
    """Special exception to signal that the execution should stop immediately."""
