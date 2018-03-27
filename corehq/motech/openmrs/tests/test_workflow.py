from __future__ import absolute_import

from unittest import TestCase

from mock import Mock

from corehq.motech.openmrs.workflow import WorkflowTask, WorkflowError, execute_workflow


class WorkflowTests(TestCase):

    def test_workflow_func_str(self):
        def run_away():
            pass

        task = WorkflowTask(func=run_away)
        self.assertEqual(str(task), 'run_away')

    def test_workflow_class_str(self):
        class RunAwayTask(WorkflowTask):
            pass

        task = RunAwayTask(func=None)
        self.assertEqual(str(task), 'RunAwayTask')

    def test_workflow_runs(self):
        """
        If no errors occur, a workflow should be executed to completion
        """
        func1 = Mock()
        func2 = Mock()
        workflow = [
            WorkflowTask(func1),
            WorkflowTask(func2),
        ]

        errors = execute_workflow(workflow)
        self.assertEqual(errors, [])
        func1.assert_called()
        func2.assert_called()
        self.assertEqual(workflow, [])

    def test_rollback_runs(self):
        """
        If an error is encountered, the workflow should stop, and the rollback should run to completion
        """
        func1 = Mock()
        black_knight_error = ValueError("'Tis but a flesh wound")
        black_knight = Mock(side_effect=black_knight_error)
        func3 = Mock()

        rollback_func1 = Mock()
        black_knight_rollback_error = ValueError("Come back here and take what's comin' ta ya!")
        rollback_black_knight = Mock(side_effect=black_knight_rollback_error)
        rollback_func3 = Mock()

        black_knight_task = WorkflowTask(func=black_knight, rollback_func=rollback_black_knight)

        workflow = [
            WorkflowTask(func=func1, rollback_func=rollback_func1),
            black_knight_task,
            WorkflowTask(func=func3, rollback_func=rollback_func3),
        ]

        errors = execute_workflow(workflow)
        self.assertEqual(errors, [
            WorkflowError(black_knight_task, black_knight_error, is_rollback_error=False),
            WorkflowError(black_knight_task, black_knight_rollback_error, is_rollback_error=True),
        ])

        # Check workflow halted on failure
        func1.assert_called()
        black_knight.assert_called()
        func3.assert_not_called()

        # Check rollback continued after error
        rollback_black_knight.assert_called()
        rollback_func1.assert_called()

    def test_returns_result(self):
        """
        WorkflowTask.returns_result should pass the result of func as an arg to rollback_func.
        """
        create_foo = Mock(return_value=5)
        delete_foo = Mock()
        fail = Mock(side_effect=Exception('Fail'))

        workflow = [
            WorkflowTask(func=create_foo, rollback_func=delete_foo, returns_result=True),
            WorkflowTask(func=fail),
        ]
        errors = execute_workflow(workflow)

        self.assertTrue(errors)
        create_foo.assert_called()
        delete_foo.assert_called_with(5)

    def test_pass_result_as(self):
        """
        WorkflowTask.pass_result_as should pass the result of func as a kwarg to rollback_func.
        """
        create_foo = Mock(return_value=5)
        delete_foo = Mock()
        fail = Mock(side_effect=Exception('Fail'))

        workflow = [
            WorkflowTask(func=create_foo, rollback_func=delete_foo, pass_result_as='foo_id'),
            WorkflowTask(func=fail),
        ]
        errors = execute_workflow(workflow)

        self.assertTrue(errors)
        create_foo.assert_called()
        delete_foo.assert_called_with(foo_id=5)

    def test_returns_subtasks(self):
        """
        WorkflowTask.returns_subtasks should add subtasks to the workflow.
        """
        func2 = Mock()
        func1 = Mock(return_value=[WorkflowTask(func=func2)])

        workflow = [
            WorkflowTask(func=func1, returns_subtasks=True),
        ]
        errors = execute_workflow(workflow)

        self.assertFalse(errors)
        func1.assert_called()
        func2.assert_called()

    def test_returns_result_subtasks(self):
        """
        returns_result and returns_subtasks should do both.
        """
        do_bar = Mock()
        create_foo = Mock(return_value=(5, [WorkflowTask(func=do_bar)]))
        delete_foo = Mock()
        fail = Mock(side_effect=Exception('Fail'))

        workflow = [
            WorkflowTask(func=create_foo, rollback_func=delete_foo, returns_result=True, returns_subtasks=True),
            WorkflowTask(func=fail),
        ]
        errors = execute_workflow(workflow)

        self.assertTrue(errors)
        create_foo.assert_called()
        do_bar.assert_called()
        delete_foo.assert_called_with(5)


class WorkflowErrorTests(TestCase):

    def test_str(self):
        def get_airspeed_velocity(bird, is_laden):
            pass

        task = WorkflowTask(func=get_airspeed_velocity, func_args=('swallow', ), func_kwargs={'is_laden': False})
        error = WorkflowError(task, TypeError('Missing argument: african_or_european'), False)
        self.assertEqual(
            str(error),
            'WorkflowTask "get_airspeed_velocity" failed: TypeError: Missing argument: african_or_european'
        )
