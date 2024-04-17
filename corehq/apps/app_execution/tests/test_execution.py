from django.test import SimpleTestCase

from . import response_factory as factory
from .mock_formplayer import CaseList, Form, Menu, MockFormplayer
from ..api import FormplayerSession, execute_workflow
from ..data_model import AnswerQuestionStep, CommandStep, EntitySelectStep, FormStep, SubmitFormStep, Workflow

CASES = [{"id": "123", "name": "Case1"}, {"id": "456", "name": "Case2"}]
APP = Menu(
    name="App1",
    children=[
        Menu(name="Case List", children=[
            CaseList(name="Followup", cases=CASES, children=[
                Form(name="Followup Case", children=[
                    factory.make_question("0", "Name", "name", "str"),
                ])
            ]),
        ]),
    ]
)


class TestDiscovery(SimpleTestCase):
    def test_execution(self):
        workflow = Workflow(steps=[
            CommandStep("Case List"),
            CommandStep("Followup"),
            EntitySelectStep("123"),
            CommandStep("Followup Case"),
            FormStep(children=[
                AnswerQuestionStep(question_text='Name', question_id='name', value='str'), SubmitFormStep()
            ])
        ])
        session = FormplayerSession(domain="domain", app_id="app_id", user_id="user_id", username="username")
        with MockFormplayer(APP):
            execute_workflow(session, workflow)
