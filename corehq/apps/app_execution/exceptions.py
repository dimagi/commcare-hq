class AppExecutionError(Exception):
    pass


class FormplayerException(Exception):
    pass


class StopExecution(Exception):
    """Special exception to signal that the execution should stop immediately."""
