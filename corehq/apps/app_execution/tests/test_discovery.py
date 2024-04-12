import dataclasses
from unittest import mock

from django.test import SimpleTestCase

from corehq.apps.app_execution.discovery import discover_workflows
from . import response_factory as factory


@dataclasses.dataclass
class Screen:
    name: str
    children: list = dataclasses.field(default_factory=list)

    def get_response_data(self, selections):
        pass


@dataclasses.dataclass
class Menu(Screen):
    def get_response_data(self, selections):
        return factory.command_response(selections, [child.name for child in self.children])


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
            Menu(name="Followup", children=[
                Form(name="Followup Case", children=[
                    factory.make_question("0", "Name", "name", "str"),
                ])
            ])
        ]),
    ]
)


@dataclasses.dataclass
class MockFormplayer:
    app: Menu
    session: dict = dataclasses.field(default_factory=dict)

    def make_request(self, session, data):
        if "navigate_menu" in session.request_url:
            selections = [int(s) for s in data["selections"]]
            option = APP1
            for selection in selections:
                option = option.children[selection]
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


class TestDiscovery(SimpleTestCase):
    def test_discovery(self):
        session = MockFormplayer(APP1)
        with mock.patch("corehq.apps.app_execution.api._make_request", new=session.make_request):
            workflows = discover_workflows("domain", "app_id", "user_id", "username")

        self.assertEquals(len(workflows), 3)
