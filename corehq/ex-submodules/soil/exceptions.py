

class TaskFailedError(Exception):
    def __init__(self, errors=None, *args, **kwargs):
        self.errors = errors
        super(TaskFailedError, self).__init__(*args, **kwargs)
