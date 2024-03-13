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


class IndexMultiplexedException(Exception):
    pass


class IndexAlreadySwappedException(Exception):
    pass
