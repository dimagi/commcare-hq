import itertools
import json

from django.test import SimpleTestCase
from testil import eq

from corehq.apps.app_execution.data_model import AppWorkflow, steps
from corehq.apps.app_manager.tests.views.test_apply_patch import assert_no_diff


class DataModelTest(SimpleTestCase):

    def test_workflow_has_all_step_types(self):
        workflow = _get_workflow()
        all_steps = []
        new_steps = [step for step in workflow.steps]
        while new_steps:
            all_steps.extend(new_steps)
            new_steps = list(itertools.chain.from_iterable([
                step.get_children() for step in new_steps if step.get_children()
            ]))
        step_types = {step.type for step in all_steps}
        missing = steps.STEP_MAP.keys() - step_types
        if missing:
            raise AssertionError(f"Missing step types: {missing}")

    def test_to_json(self):
        assert_json_dict_equal(_get_workflow().__jsonattrs_to_json__(), _get_workflow_json())

    def test_from_json(self):
        workflow = AppWorkflow.__jsonattrs_from_json__(_get_workflow_json())
        eq(workflow, _get_workflow())


def assert_json_dict_equal(expected, actual):
    if expected != actual:
        assert_no_diff(json.dumps(expected, indent=2), json.dumps(actual, indent=2))


def _get_workflow():
    return AppWorkflow(steps=[
        steps.CommandStep("Case Search"),
        steps.QueryInputValidationStep({"first_name": "query value"}),
        steps.QueryInputValidationStep({"last_name": "query value"}),
        steps.QueryStep({"first_name": "query value", "last_name": "query value"}),
        steps.EntitySelectStep("123"),
        steps.EntitySelectIndexStep(2),
        steps.ClearQueryStep(),
        steps.RawNavigationStep(request_data={"selections": ["0", "1", "123abc"]}),
        steps.CommandStep("Followup Case"),
        steps.MultipleEntitySelectStep(values=["xyz", "abc"]),
        steps.MultipleEntitySelectByIndexStep(values=[0, 2]),
        steps.FormStep(children=[
            steps.AnswerQuestionStep(question_text='Name', question_id='name', value='str'),
            steps.SubmitFormStep()
        ]),
    ])


def _get_workflow_json():
    return {
        "steps": [
            {"type": "command", "value": "Case Search"},
            {"type": "query_input_validation", "inputs": {"first_name": "query value"}},
            {"type": "query_input_validation", "inputs": {"last_name": "query value"}},
            {
                "type": "query",
                "inputs": {"first_name": "query value", "last_name": "query value"},
                "validate_inputs": False,
            },
            {"type": "entity_select", "value": "123"},
            {"type": "entity_select_index", "value": 2},
            {"type": "clear_query"},
            {"type": "raw_navigation", "request_data": {"selections": ["0", "1", "123abc"]}},
            {"type": "command", "value": "Followup Case"},
            {"type": "multiple_entity_select", "values": ["xyz", "abc"]},
            {"type": "multiple_entity_select_by_index", "values": [0, 2]},
            {
                "type": "form",
                "children": [
                    {
                        "type": "answer_question",
                        "question_text": "Name",
                        "question_id": "name",
                        "value": "str",
                    },
                    {"type": "submit_form"}
                ]
            }
        ]
    }
