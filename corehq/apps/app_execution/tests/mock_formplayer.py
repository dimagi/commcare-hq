import dataclasses
from functools import cached_property
from unittest import mock

from corehq.apps.app_execution.tests import response_factory as factory


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
    cases: list = dataclasses.field(default_factory=list)

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


@dataclasses.dataclass
class MockFormplayer:
    app: Menu
    session: dict = dataclasses.field(default_factory=dict)

    def __enter__(self):
        self._patch = mock.patch("corehq.apps.app_execution.api._make_request", new=self.process_request)
        self._patch.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._patch.stop()
        self._patch = None

    def process_request(self, session, data, url):
        if "navigate_menu" in url:
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
            assert data.get("session_id") == self.session["session_id"]
            if data["action"] == "answer":
                self.session["tree"][int(data["ix"])]["answer"] = data["answer"]
            elif data["action"] == "submit-all":
                return {"submitResponseMessage": "success", "nextScreen": None}
            return self.session
