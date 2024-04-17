from django.test import SimpleTestCase
from testil import eq

from corehq.apps.app_execution.data_model import (
    AnswerQuestionStep, CommandStep, EntitySelectStep, FormStep, QueryStep,
    SubmitFormStep, Workflow,
)


class DataModelTest(SimpleTestCase):

    def test_to_dict(self):
        workflow = Workflow(steps=[
            CommandStep("Case Search"),
            QueryStep({"first_name": "query value", "last_name": "query value"}),
            EntitySelectStep("123"),
            CommandStep("Followup Case"),
            FormStep(children=[
                AnswerQuestionStep(question_text='Name', question_id='name', value='str'), SubmitFormStep()
            ])
        ])
        eq(workflow.to_dict(), {
            "steps": [
                {"type": "command", "value": "Case Search"},
                {"type": "query", "inputs": {"first_name": "query value", "last_name": "query value"}},
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
        })

    def test_from_dict(self):
        workflow = Workflow.from_dict({
            "steps": [
                {"type": "command", "value": "Case Search"},
                {"type": "query", "inputs": {"first_name": "query value", "last_name": "query value"}},
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
        })
        eq(workflow, Workflow(steps=[
            CommandStep("Case Search"),
            QueryStep({"first_name": "query value", "last_name": "query value"}),
            EntitySelectStep("123"),
            CommandStep("Followup Case"),
            FormStep(children=[
                AnswerQuestionStep(question_text='Name', question_id='name', value='str'), SubmitFormStep()
            ])
        ]))
