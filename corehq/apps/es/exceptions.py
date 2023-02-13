class ESError(Exception):
    pass


class ESShardFailure(ESError):
    pass


class TaskError(ESError):

    def __init__(self, tasks_result):
        self.tasks_result = tasks_result
        super().__init__(tasks_result)


class TaskMissing(TaskError):
    pass


class IndexNotMultiplexedException(Exception):
    pass


class UnknownDocException(Exception):
    def __init__(self, expected_cls, actual):
        msg = f"Expected doc to be of type {expected_cls.__name__}, got {actual.__class__.__name__}"
        super().__init__(msg)


class InvalidDictForAdapter(Exception):
    pass
