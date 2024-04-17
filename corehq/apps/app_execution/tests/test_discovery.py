from django.test import SimpleTestCase
from testil import eq

from . import response_factory as factory
from .mock_formplayer import CaseList, Form, Menu, MockFormplayerClient
from ..data_model import AnswerQuestionStep, CommandStep, EntitySelectStep, FormStep, SubmitFormStep, Workflow
from ..discovery import discover_workflows

CASES = [{"id": "123", "name": "Case1"}, {"id": "456", "name": "Case2"}]
APP = Menu(
    name="App1",
    children=[
        Menu(name="Survey", children=[
            Form(name="Form1", children=[
                factory.make_question("0", "Name", "name", "str"),
            ])
        ]),
        Menu(name="Case List", children=[
            Menu(name="Register", children=[
                Form(name="Register Case", children=[
                    factory.make_question("0", "Name", "name", "str"),
                ])
            ]),
            CaseList(name="Followup", cases=CASES, children=[
                Form(name="Followup Case", children=[
                    factory.make_question("0", "Name", "name", "str"),
                ])
            ]),
        ]),
    ]
)


class TestDiscovery(SimpleTestCase):
    def test_discovery(self):
        workflows = discover_workflows(MockFormplayerClient(APP), "app_id")

        eq(len(workflows), 3)
        form_step = FormStep(children=[
            AnswerQuestionStep(question_text='Name', question_id='name', value='str'), SubmitFormStep()
        ])

        eq(workflows, [
            Workflow(steps=[
                CommandStep("Survey"),
                CommandStep("Form1"),
                form_step
            ]),
            Workflow(steps=[
                CommandStep("Case List"),
                CommandStep("Register"),
                CommandStep("Register Case"),
                form_step
            ]),
            Workflow(steps=[
                CommandStep("Case List"),
                CommandStep("Followup"),
                EntitySelectStep("123"),
                CommandStep("Followup Case"),
                form_step
            ]),
        ])
