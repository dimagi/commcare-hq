from django.test import SimpleTestCase
from testil import eq

from . import response_factory as factory
from .mock_formplayer import CaseList, CaseSearch, Form, Menu, MockFormplayerClient
from ..data_model import AnswerQuestionStep, CommandStep, EntitySelectStep, FormStep, QueryStep, SubmitFormStep, \
    AppWorkflow
from ..discovery import discover_workflows

CASES = [{"id": "123", "name": "Case1"}, {"id": "456", "name": "Case2"}]
SEARCH_DISPLAYS = [
    {"id": "first_name", "value": "", "required": True, "allow_blank_value": False},
    {"id": "last_name", "value": "", "required": True, "allow_blank_value": False},
    {"id": "dob", "value": "", "required": False, "allow_blank_value": False},
]

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
        CaseSearch(name="Case Search", query_key="m1.search", displays=SEARCH_DISPLAYS, children=[
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

        eq(len(workflows), 4)
        form_step = FormStep(children=[
            AnswerQuestionStep(question_text='Name', question_id='name', value='str'), SubmitFormStep()
        ])

        eq(workflows, [
            AppWorkflow(steps=[
                CommandStep("Survey"),
                CommandStep("Form1"),
                form_step
            ]),
            AppWorkflow(steps=[
                CommandStep("Case List"),
                CommandStep("Register"),
                CommandStep("Register Case"),
                form_step
            ]),
            AppWorkflow(steps=[
                CommandStep("Case Search"),
                QueryStep({"first_name": "query value", "last_name": "query value"}),
                EntitySelectStep("123"),
                CommandStep("Followup Case"),
                form_step
            ]),
            AppWorkflow(steps=[
                CommandStep("Case List"),
                CommandStep("Followup"),
                EntitySelectStep("123"),
                CommandStep("Followup Case"),
                form_step
            ]),
        ])
