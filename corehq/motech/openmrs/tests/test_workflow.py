from __future__ import absolute_import
from django.test import SimpleTestCase
from mock import Mock

from corehq.motech.openmrs.workflow import Task, WorkflowTask, execute_workflow, task, workflow_task


class TaskTests(SimpleTestCase):

    def test_task_run_func_args_kwargs(self):
        """
        Task.run_func should call func with the args and kwargs that the task was instantiated with.
        """
        sing = Mock()
        func_task = Task(sing, 'Brave Sir Robin', what='ran', where='away')

        self.assertEqual(func_task.func, sing)
        self.assertEqual(func_task.args, ('Brave Sir Robin',))
        self.assertEqual(func_task.kwargs, {'what': 'ran', 'where': 'away'})
        sing.assert_not_called()

        func_task.run_func()
        sing.assert_called_with('Brave Sir Robin', what='ran', where='away')

    def test_task_run(self):
        """
        Task.run should be called if the task was not instantiated with func
        """
        class SirRobin(Task):
            def run(self):
                pass

        sir_robin = SirRobin(None, 'fled', tail='turned', where='away')
        sir_robin.run = Mock()

        sir_robin.run_func()
        sir_robin.run.assert_called_with('fled', tail='turned', where='away')


class WorkflowTests(SimpleTestCase):

    def test_workflow_runs(self):
        """
        If no errors occur, a workflow should be executed to completion
        """
        func1 = Mock()
        func2 = Mock()
        workflow_queue = [
            WorkflowTask(None, None, func1),
            WorkflowTask(None, None, func2),
        ]

        success, errors = execute_workflow(workflow_queue)
        self.assertTrue(success)
        self.assertEqual(errors, [])
        func1.assert_called()
        func2.assert_called()
        self.assertEqual(workflow_queue, [])

    def test_rollback_runs(self):
        """
        If an error is encountered, the workflow should stop, and the rollback should run to completion
        """
        func1 = Mock()
        black_knight = Mock(side_effect=ValueError("'Tis but a flesh wound"))
        func3 = Mock()

        rollback_func1 = Mock()
        rollback_black_knight = Mock(side_effect=ValueError("Come back here and take what's comin' ta ya!"))
        rollback_func3 = Mock()

        workflow_queue = [
            WorkflowTask(Task(rollback_func1), None, func1),
            WorkflowTask(Task(rollback_black_knight), None, black_knight),
            WorkflowTask(Task(rollback_func3), None, func3),
        ]

        success, errors = execute_workflow(workflow_queue)
        self.assertFalse(success)
        self.assertEqual(errors, [
            "Workflow failed: ValueError: 'Tis but a flesh wound",
            "Rollback error: ValueError: Come back here and take what's comin' ta ya!",
        ])

        # Check workflow halted on failure
        func1.assert_called()
        black_knight.assert_called()
        func3.assert_not_called()

        # Check rollback continued after error
        rollback_black_knight.assert_called()
        rollback_func1.assert_called()

        # Last task should still be languishing in the workflow queue
        self.assertEqual(len(workflow_queue), 1)
        self.assertEqual(workflow_queue[0].func, func3)

    def test_pass_result_as(self):
        """
        WorkflowTask.pass_result_as should pass the result of run_func to its rollback task using the given
        parameter name.
        """
        create_foo = Mock(return_value=5)
        delete_foo = Mock()
        fail = Mock(side_effect=Exception('Fail'))

        workflow_queue = [
            WorkflowTask(Task(delete_foo), 'foo_id', create_foo),
            WorkflowTask(None, None, fail),
        ]
        success, errors = execute_workflow(workflow_queue)

        self.assertFalse(success)
        create_foo.assert_called()
        delete_foo.assert_called_with(foo_id=5)


class DecoratorTests(SimpleTestCase):

    def test_task_decorator(self):
        """
        The `@task` decorator should return a function that creates a Task instance when it is executed
        """
        do_something = Mock()

        @task
        def get_foo_task(param1, param2):
            do_something(param1, where=param2)

        foo_task = get_foo_task('ran', param2='away')

        self.assertIsInstance(foo_task, Task)
        self.assertEqual(foo_task.args, ('ran',))
        self.assertEqual(foo_task.kwargs, {'param2': 'away'})
        do_something.assert_not_called()

        foo_task.run_func()
        do_something.assert_called_with('ran', where='away')

    def test_workflow_task_decorator(self):
        """
        The `@workflow_task` decorator should return a function that creates a WorkflowTask instance
        """
        do_something = Mock()

        @workflow_task()
        def get_foo_task(param1, param2):
            do_something(param1, where=param2)

        foo_task = get_foo_task('ran', param2='away')

        self.assertIsInstance(foo_task, WorkflowTask)
        self.assertIsNone(foo_task.rollback_task)
        self.assertIsNone(foo_task.pass_result_as)
        self.assertEqual(foo_task.args, ('ran',))
        self.assertEqual(foo_task.kwargs, {'param2': 'away'})
        do_something.assert_not_called()

        foo_task.run_func()
        do_something.assert_called_with('ran', where='away')

    def test_workflow_task_decorator_with_rollback(self):
        """
        The @workflow_task decorator should be able to set `rollback_task` and `pass_result_as`
        """
        create_foo = Mock(return_value=5)
        delete_foo = Mock()
        fail = Mock(side_effect=Exception('Fail'))

        @task
        def get_delete_foo_task(foo_id):
            delete_foo(foo_id)

        @workflow_task(rollback_task=get_delete_foo_task(), pass_result_as='foo_id')
        def get_create_foo_task(foo_name):
            foo_id = create_foo(foo_name)
            return foo_id

        workflow_queue = [
            get_create_foo_task('FOO'),
            workflow_task()(fail),
        ]
        success, errors = execute_workflow(workflow_queue)

        self.assertFalse(success)
        create_foo.assert_called_with('FOO')
        delete_foo.assert_called_with(5)
