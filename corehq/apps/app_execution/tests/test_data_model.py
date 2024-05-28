import itertools
import json

from django.test import SimpleTestCase
from testil import eq

from corehq.apps.app_execution import data_model
from corehq.apps.app_execution.data_model import STEP_MAP
from corehq.apps.app_manager.tests.views.test_apply_patch import assert_no_diff


class DataModelTest(SimpleTestCase):

    def test_workflow_has_all_step_types(self):
        workflow = _get_workflow()
        steps = []
        new_steps = [step for step in workflow.steps]
        while new_steps:
            steps.extend(new_steps)
            new_steps = list(itertools.chain.from_iterable([
                step.get_children() for step in new_steps if step.get_children()
            ]))
        step_types = {step.type for step in steps}
        missing = STEP_MAP.keys() - step_types
        if missing:
            raise AssertionError(f"Missing step types: {missing}")

    def test_to_json(self):
        assert_json_dict_equal(_get_workflow().__jsonattrs_to_json__(), _get_workflow_json())

    def test_from_json(self):
        workflow = data_model.AppWorkflow.__jsonattrs_from_json__(_get_workflow_json())
        eq(workflow, _get_workflow())


def assert_json_dict_equal(expected, actual):
    if expected != actual:
        assert_no_diff(json.dumps(expected, indent=2), json.dumps(actual, indent=2))


def _get_workflow():
    return data_model.AppWorkflow(steps=[
        data_model.CommandStep("Case Search"),
        data_model.QueryInputValidationStep({"first_name": "query value"}),
        data_model.QueryInputValidationStep({"last_name": "query value"}),
        data_model.QueryStep({"first_name": "query value", "last_name": "query value"}),
        data_model.EntitySelectStep("123"),
        data_model.EntitySelectIndexStep(2),
        data_model.ClearQueryStep(),
        data_model.RawNavigationStep(request_data={"selections": ["0", "1", "123abc"]}),
        data_model.CommandStep("Followup Case"),
        data_model.MultipleEntitySelectStep(values=["xyz", "abc"]),
        data_model.MultipleEntitySelectByIndexStep(values=[0, 2]),
        data_model.FormStep(children=[
            data_model.AnswerQuestionStep(question_text='Name', question_id='name', value='str'),
            data_model.SubmitFormStep()
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
