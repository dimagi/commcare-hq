from __future__ import absolute_import

from collections import namedtuple


class WorkflowTask(object):
    """
    WorkflowTasks are instantiated with a function to run, and args and
    kwargs that must be passed to it.

    If a task is not instantiated with a function, it must implement
    its own run() method.

    `WorkflowTask.run()` can return subtasks, which will be prepended
    to the workflow queue. If a task needs to make more than one
    change, it should split them up into subtasks.

    A WorkflowTask can accept a rollback_func when it is instantiated,
    or its rollback() method can be overridden. If rollback_func needs
    values set by `func`, then the `run()` method should add them to
    `rollback_args` or `rollback_kwargs`.
    """
    def __init__(self, func, func_args=None, func_kwargs=None,
                 rollback_func=None, rollback_args=None, rollback_kwargs=None,
                 pass_result=False, pass_result_as=None):
        """
        Instantiate WorkflowTask
        """
        self.func = func
        self.func_args = func_args or []
        self.func_kwargs = func_kwargs or {}

        self.rollback_func = rollback_func
        self.rollback_args = rollback_args or []
        self.rollback_kwargs = rollback_kwargs or {}

        self.pass_result = pass_result or pass_result_as
        self.pass_result_as = pass_result_as

    def __str__(self):
        return self.func.__name__ if self.func else self.__class__.__name__

    def run(self):
        if self.func:
            result = self.func(*self.func_args, **self.func_kwargs)
            if self.pass_result:
                if self.pass_result_as:
                    self.rollback_kwargs[self.pass_result_as] = result
                else:
                    self.rollback_args.append(result)
        else:
            raise NotImplementedError('Task.func must be set, or Task.run() must be defined.')

    def rollback(self):
        if self.rollback_func:
            return self.rollback_func(*self.rollback_args, **self.rollback_kwargs)


WorkflowError = namedtuple('WorkflowError', 'task exception is_rollback_error')


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
            assert hasattr(subtasks, '__iter__') and all(isinstance(t, WorkflowTask) for t in subtasks), \
                'Error running WorkflowTask "{}". run() should return subtasks or None. Got {} instead'.format(
                    task, repr(subtasks))
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
