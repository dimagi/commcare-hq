from django.test import SimpleTestCase

from . import response_factory as factory
from .mock_formplayer import CaseList, Form, Menu, MockFormplayerClient
from ..api import FormplayerSession, execute_workflow
from ..data_model import AnswerQuestionStep, CommandStep, EntitySelectStep, FormStep, SubmitFormStep, AppWorkflow

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
            CommandStep("Case List"),
            CommandStep("Followup"),
            EntitySelectStep("123"),
            CommandStep("Followup Case"),
            FormStep(children=[
                AnswerQuestionStep(question_text='Name', question_id='name', value='str'), SubmitFormStep()
            ])
        ])
        session = FormplayerSession(MockFormplayerClient(APP), app_id="app_id")
        session.__dict__["app_build_id"] = "app_build_id"  # prime cache to avoid DB hit
        execute_workflow(session, workflow)
