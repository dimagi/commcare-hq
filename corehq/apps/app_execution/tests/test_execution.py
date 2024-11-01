from django.test import SimpleTestCase
from testil import eq

from . import response_factory as factory
from .mock_formplayer import CaseList, Form, Menu, MockFormplayerClient
from ..api import FormplayerSession, execute_workflow
from ..data_model import AppWorkflow, steps

CASES = [{"id": "123", "name": "Case1"}, {"id": "456", "name": "Case2"}]
APP = Menu(
    name="App1",
    children=[
        Menu(name="Case List", children=[
            CaseList(name="Followup", cases=CASES, children=[
                Form(name="Followup Case", children=[
                    factory.make_question("0", "Name", "name", ""),
                ])
            ]),
        ]),
    ]
)


class TestExecution(SimpleTestCase):
    def test_execution(self):
        workflow = AppWorkflow(steps=[
            steps.CommandStep("Case List"),
            steps.CommandStep("Followup"),
            steps.EntitySelectStep("123"),
            steps.CommandStep("Followup Case"),
            steps.FormStep(children=[
                steps.AnswerQuestionStep(question_text='Name', value='str'),
                steps.SubmitFormStep(),
            ])
        ])
        session = FormplayerSession(MockFormplayerClient(APP), app_id="app_id")
        session.__dict__["app_build_id"] = "app_build_id"  # prime cache to avoid DB hit
        success = execute_workflow(session, workflow)
        eq(success, True)
