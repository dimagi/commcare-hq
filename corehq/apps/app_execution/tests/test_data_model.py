from django.test import SimpleTestCase
from testil import eq

from corehq.apps.app_execution.data_model import (
    AnswerQuestionStep, CommandStep, EntitySelectStep, FormStep, QueryStep,
    SubmitFormStep, AppWorkflow,
)


class DataModelTest(SimpleTestCase):

    def test_to_json(self):
        eq(_get_workflow().__jsonattrs_to_json__(), _get_workflow_json())

    def test_from_json(self):
        workflow = AppWorkflow.__jsonattrs_from_json__(_get_workflow_json())
        eq(workflow, _get_workflow())


def _get_workflow():
    return AppWorkflow(steps=[
        CommandStep("Case Search"),
        QueryStep({"first_name": "query value", "last_name": "query value"}),
        EntitySelectStep("123"),
        CommandStep("Followup Case"),
        FormStep(children=[
            AnswerQuestionStep(question_text='Name', question_id='name', value='str'),
            SubmitFormStep()
        ]),
    ])


def _get_workflow_json():
    return {
        "steps": [
            {"type": "command", "value": "Case Search"},
            {
                "type": "query",
                "inputs": {"first_name": "query value", "last_name": "query value"},
                "validate_inputs": False,
            },
            {"type": "entity_select", "value": "123"},
            {"type": "command", "value": "Followup Case"},
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
