from django.test import SimpleTestCase
from testil import eq

from corehq.apps.app_execution import data_model
from corehq.apps.app_execution.data_model import AppWorkflow
from corehq.apps.app_execution.exceptions import AppExecutionError
from corehq.apps.app_execution.tests.test_expectations import get_workflow_with_all_expectation_steps
from corehq.apps.app_execution.tests.test_steps import get_workflow_with_all_steps
from corehq.apps.app_execution.workflow_dsl import DSL_MAP, dsl_to_workflow, workflow_to_dsl
from corehq.apps.app_manager.tests.views.test_apply_patch import assert_no_diff


class TestDsl(SimpleTestCase):

    def test_map_has_all_steps(self):
        missing = set(DSL_MAP) - set(data_model.steps.STEP_MAP) - set(data_model.expectations.TYPE_MAP)
        self.assertEqual(missing, set())

    def test_workflow_to_dsl(self):
        workflow = _get_workflow()
        dsl = workflow_to_dsl(workflow)
        assert_no_diff(_get_dsl(), dsl)

    def test_dsl_to_workflow(self):
        workflow = dsl_to_workflow(_get_dsl())
        eq(workflow, _get_workflow())

    def test_dsl_to_workflow_invalid_step(self):
        dsl = "make me a sandwich"
        message = "Invalid step: make me a sandwich"
        with self.assertRaisesMessage(AppExecutionError, message):
            dsl_to_workflow(dsl)

    def test_dsl_blank_lines_and_comments(self):
        dsl = """
        # blank lines and comments are ignored
        Select menu "Case Search"

        # indents are ignored
            Select menu with ID "action 0"
        """
        workflow = dsl_to_workflow(dsl)
        eq(workflow, data_model.AppWorkflow(steps=[
            data_model.steps.CommandStep("Case Search"),
            data_model.steps.CommandIdStep("action 0"),
        ]))

    def test_expectations_in_form(self):
        dsl = """
        Start form
            Expect case present @case_id = '123'
            Answer question "Name" with "str"
            Expect question "/data/question1" with "123"
            Submit form
        End form
        """
        workflow = dsl_to_workflow(dsl)
        eq(workflow, data_model.AppWorkflow(steps=[
            data_model.steps.FormStep(children=[
                data_model.expectations.CasePresent(xpath_filter="@case_id = '123'"),
                data_model.steps.AnswerQuestionStep("Name", "str"),
                data_model.expectations.QuestionValue("/data/question1", "123"),
                data_model.steps.SubmitFormStep(),
            ]),
        ]))


def _get_workflow():
    steps = get_workflow_with_all_steps().steps
    expectations = get_workflow_with_all_expectation_steps().steps
    return AppWorkflow(steps=steps + expectations)


def _get_dsl():
    lines = [
        'Select menu "Case Search"',
        'Select menu with ID "action 0"',
        'Update search parameters first_name="query value"',
        'Update search parameters last_name="query value"',
        'Search with parameters first_name="query value", last_name="query value"',
        'Select entity with ID "123"',
        'Select entity at index 2',
        'Clear search',
        'Raw navigation request data {"selections": ["0", "1", "123abc"]}',
        'Select menu "Followup Case"',
        'Select entities with IDs "xyz, abc"',
        'Select entities at indexes 0, 2',
        'Start form',
        '  Answer question "Name" with "str"',
        '  Answer question with ID "name" with "str"',
        '  Submit form',
        'End form',
        "Expect xpath instance('commcaresession')/session/data/case/@case_id = '123'",
        "Expect case present @case_id = '123'",
        "Expect case absent @case_id = '345'",
        'Expect question "/data/question1" with "123"',
    ]
    return '\n'.join(lines)
