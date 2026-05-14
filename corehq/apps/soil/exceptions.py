

class TaskFailedError(Exception):

    def __init__(self, errors=None, exception_name=None, *args, **kwargs):
        self.errors = errors
        self.exception_name = exception_name
        super(TaskFailedError, self).__init__(*args, **kwargs)
