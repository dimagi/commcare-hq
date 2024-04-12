import dataclasses
from functools import cached_property
from unittest import mock

from testil import eq

from . import response_factory as factory
from ..data_model import AnswerQuestionStep, CommandStep, EntitySelectStep, FormStep, SubmitFormStep, Workflow
from ..discovery import discover_workflows


@dataclasses.dataclass
class Screen:
    name: str
    children: list

    def process_selections(self, selections):
        option = self
        for selection in selections:
            option = option.get_next(selection)
        return option

    def get_next(self, selection):
        return self.children[int(selection)]

    def get_response_data(self, selections):
        pass


@dataclasses.dataclass
class Menu(Screen):
    def get_response_data(self, selections):
        return factory.command_response(selections, [child.name for child in self.children])


@dataclasses.dataclass
class CaseList(Screen):
    cases: list[str] = dataclasses.field(default_factory=list)

    @cached_property
    def entities(self):
        return factory.make_entities(self.cases)

    def get_response_data(self, selections):
        return factory.entity_list_response(selections, self.entities)

    def get_next(self, selection):
        assert selection in [e["id"] for e in self.entities], selection
        return Menu(name="Forms", children=self.children)


@dataclasses.dataclass
class Form(Screen):

    def get_response_data(self, selections):
        return factory.form_response(selections, self.children)


APP1 = Menu(
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
            CaseList(name="Followup", cases=["Case1", "Case2"], children=[
                Form(name="Followup Case", children=[
                    factory.make_question("0", "Name", "name", "str"),
                ])
            ]),
        ]),
    ]
)


@dataclasses.dataclass
class MockFormplayer:
    app: Menu
    session: dict = dataclasses.field(default_factory=dict)

    def process_request(self, session, data):
        if "navigate_menu" in session.request_url:
            selections = data["selections"]
            option = self.app.process_selections(selections)
            data = option.get_response_data(selections)
            if isinstance(option, Form):
                self.session = data
            return data
        else:
            # form response
            if not self.session:
                raise ValueError("No session data")
            if data["action"] == "answer":
                self.session["tree"][int(data["idx"])]["answer"] = data["answer"]
            elif data["action"] == "submit-all":
                return {"submitResponseMessage": "success", "nextScreen": None}
            return self.session


def test_discovery():
    session = MockFormplayer(APP1)
    with mock.patch("corehq.apps.app_execution.api._make_request", new=session.process_request):
        workflows = discover_workflows("domain", "app_id", "user_id", "username")

    eq(len(workflows), 3)
    form_step = FormStep(children=[
        AnswerQuestionStep(question_text='Name', question_id='name', value='str'), SubmitFormStep()
    ])

    selected_case_id = APP1.process_selections([1, 1]).entities[0]["id"]
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
            EntitySelectStep(selected_case_id),
            CommandStep("Followup Case"),
            form_step
        ]),
    ])
