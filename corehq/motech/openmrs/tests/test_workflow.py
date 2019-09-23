import unittest

from mock import Mock

from corehq.motech.openmrs.workflow import (
    WorkflowError,
    WorkflowTask,
    execute_workflow,
)


class WorkflowTests(unittest.TestCase):

    def test_workflow_class_str(self):
        class RunAwayTask(WorkflowTask):
            def run(self):
                pass

        task = RunAwayTask()
        self.assertEqual(str(task), 'RunAwayTask')

    def test_workflow_runs(self):
        """
        If no errors occur, a workflow should be executed to completion
        """
        func1 = Mock()
        func2 = Mock()

        class Task1(WorkflowTask):
            def run(self):
                func1()

        class Task2(WorkflowTask):
            def run(self):
                func2()

        workflow = [
            Task1(),
            Task2(),
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
        rollback1 = Mock()

        black_knight_error = ValueError("'Tis but a flesh wound")
        black_knight = Mock(side_effect=black_knight_error)
        black_knight_rollback_error = ValueError("Come back here and take what's comin' ta ya!")
        black_knight_rollback = Mock(side_effect=black_knight_rollback_error)

        func3 = Mock(return_value=None)

        class Task1(WorkflowTask):
            def run(self):
                func1()
            def rollback(self):
                rollback1()

        class BlackKnightTask(WorkflowTask):
            def run(self):
                black_knight()
            def rollback(self):
                black_knight_rollback()

        class Task3(WorkflowTask):
            def run(self):
                func3()

        black_knight_task = BlackKnightTask()

        workflow = [
            Task1(),
            black_knight_task,
            Task3(),
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
        black_knight_rollback.assert_called()
        func1.assert_called()


class WorkflowErrorTests(unittest.TestCase):

    def test_str(self):
        class AirspeedVelocityTask(WorkflowTask):
            def run(self):
                raise TypeError('Missing argument: african_or_european')

        workflow = [AirspeedVelocityTask()]
        errors = execute_workflow(workflow)
        self.assertEqual(
            str(errors[0]),
            'AirspeedVelocityTask.run() failed: TypeError: Missing argument: african_or_european'
        )
