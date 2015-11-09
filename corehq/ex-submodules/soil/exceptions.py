

class TaskFailedError(Exception):
    def __init__(self, errors, *args, **kwargs):
        self.errors = errors
        super(TaskFailedError, self).__init__(*args, **kwargs)
