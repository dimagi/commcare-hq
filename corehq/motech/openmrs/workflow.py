from collections import namedtuple


class WorkflowTask(object):
    """
    WorkflowTask subclasses must must implement the run() method.

    Any changes made by run() should be reversed by rollback().

    run() can return subtasks, which will be prepended
    to the workflow queue. If a task needs to make more than one
    change, it should split them up into subtasks.
    """
    def __str__(self):
        return self.__class__.__name__

    def run(self):
        raise NotImplementedError

    def rollback(self):
        pass


class WorkflowError(namedtuple('WorkflowError', 'task error is_rollback_error')):

    def __str__(self):
        return '{task}{run_or_rollback} failed: {exception}: {error}'.format(
            task=self.task,
            run_or_rollback='.rollback()' if self.is_rollback_error else '.run()',
            exception=self.error.__class__.__name__,
            error=self.error
        )


def execute_workflow(workflow):
    errors = []
    executed_tasks = []

    while workflow:
        task = workflow.pop(0)
        # .. NOTE: The task is added to executed_tasks before it is
        #          actually run. This allows its rollback() method
        #          the opportunity to clean up anything that might
        #          have happened at the point of failure.
        executed_tasks.append(task)
        try:
            subtasks = task.run() or []
            if not (hasattr(subtasks, '__iter__') and all(isinstance(t, WorkflowTask) for t in subtasks)):
                raise ValueError(
                    'Error running WorkflowTask "{}": '
                    'run() should return subtasks or None. Got {} instead'.format(task, repr(subtasks))
                )
        except Exception as err:
            errors.append(WorkflowError(task, err, False))
            for task in reversed(executed_tasks):
                try:
                    task.rollback()
                except Exception as err:
                    errors.append(WorkflowError(task, err, True))
            break
        else:
            workflow[0:0] = subtasks

    return errors
