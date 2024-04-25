from __future__ import annotations

import dataclasses
from typing import ClassVar

from attr import define
from attrs import asdict

from corehq.apps.app_execution.exceptions import AppExecutionError


@define
class Step:
    type: ClassVar[str]
    is_form_step: ClassVar[bool]

    def get_request_data(self, session, data):
        return data

    def get_children(self):
        return []

    def to_json(self):
        return {"type": self.type, **asdict(self)}

    @classmethod
    def from_json(cls, data):
        return cls(**data)


@define
class AppWorkflow:
    steps: list[Step] = dataclasses.field(default_factory=list)

    def __jsonattrs_to_json__(self):
        return {
            "steps": [step.to_json() for step in self.steps]
        }

    @classmethod
    def __jsonattrs_from_json__(cls, data):
        return cls(steps=_steps_from_json(data["steps"]))

    def __str__(self):
        return " -> ".join(str(step) for step in self.steps)


@define
class CommandStep(Step):
    type: ClassVar[str] = "command"
    is_form_step: ClassVar[bool] = False
    value: str

    def get_request_data(self, session, data):
        commands = {c["displayText"].lower(): c for c in session.data.get("commands", [])}

        try:
            command = commands[self.value.lower()]
        except KeyError:
            raise AppExecutionError(f"Command not found: {self.value}: {commands.keys()}")
        return _append_selection(data, command["index"])


@define
class EntitySelectStep(Step):
    type: ClassVar[str] = "entity_select"
    is_form_step: ClassVar[bool] = False
    value: str

    def get_request_data(self, session, data):
        entities = {entity["id"] for entity in session.data.get("entities", [])}
        if not entities:
            raise AppExecutionError("No entities found")
        if self.value not in entities:
            raise AppExecutionError(f"Entity not found: {self.value}: {list(entities)}")
        return _append_selection(data, self.value)

    def __str__(self):
        return f"Entity Select: {self.value}"


@define
class EntitySelectIndexStep(Step):
    type: ClassVar[str] = "entity_select_index"
    is_form_step: ClassVar[bool] = False
    value: int

    def get_request_data(self, session, data):
        entities = [entity["id"] for entity in session.data.get("entities", [])]
        if not entities:
            raise AppExecutionError("No entities found")
        if self.value >= len(entities):
            raise AppExecutionError(f"Entity index out of range: {self.value}: {list(entities)}")
        return _append_selection(data, entities[self.value])

    def __str__(self):
        return f"Entity Select: {self.value}"


@define
class QueryStep(Step):
    type: ClassVar[str] = "query"
    is_form_step: ClassVar[bool] = False
    inputs: dict

    def get_request_data(self, session, data):
        query_key = session.data["queryKey"]
        return {
            **data,
            "query_data": {
                query_key: {
                    "execute": True,
                    "inputs": self.inputs,
                }
            },
        }

    def __str__(self):
        return f"Query: {self.inputs}"


@define
class AnswerQuestionStep(Step):
    type: ClassVar[str] = "answer_question"
    is_form_step: ClassVar[bool] = True
    question_text: str
    question_id: str
    value: str

    def get_request_data(self, session, data):
        try:
            question = [
                node for node in session.data["tree"]
                if (
                    (self.question_text and node["caption"] == self.question_text)
                    or (self.question_id and node["question_id"] == self.question_id)
                )
            ][0]
        except IndexError:
            raise AppExecutionError(f"Question not found: {self.question_text or self.question_id}")

        return {
            **data,
            "action": "answer",
            "answersToValidate": {},
            "answer": self.value,
            "ix": question["ix"],
            "session_id": session.data["session_id"]
        }

    def __str__(self):
        return f"Answer Question: {self.question_text or self.question_id} = {self.value}"


@define
class SubmitFormStep(Step):
    type: ClassVar[str] = "submit_form"
    is_form_step: ClassVar[bool] = True

    def get_request_data(self, session, data):
        answers = {
            node["ix"]: node["answer"]
            for node in session.data["tree"]
            if "answer" in node
        }
        return {
            **data,
            "action": "submit-all",
            "prevalidated": True,
            "answers": answers,
            "session_id": session.data["session_id"]
        }


@define
class FormStep(Step):
    type: ClassVar[str] = "form"
    children: list[AnswerQuestionStep | SubmitFormStep]
    is_form_step: ClassVar[bool] = True

    def to_json(self):
        return {
            "type": self.type,
            "children": [child.to_json() for child in self.children]
        }

    def get_children(self):
        return self.children

    @classmethod
    def from_json(cls, data):
        return cls(children=_steps_from_json(data["children"]))


def _append_selection(data, selection):
    selections = data.get("selections", [])
    selections.append(selection)
    return {**data, "selections": selections}


STEP_MAP = {
    "command": CommandStep,
    "entity_select": EntitySelectStep,
    "entity_select_index": EntitySelectIndexStep,
    "query": QueryStep,
    "answer_question": AnswerQuestionStep,
    "submit_form": SubmitFormStep,
    "form": FormStep,
}


def _steps_from_json(data):
    return [STEP_MAP[child.pop("type")].from_json(child) for child in data]


EXAMPLE_WORKFLOW = AppWorkflow(steps=[
    CommandStep(value="My Module"),
    EntitySelectStep(value="clinic_123"),
    QueryStep(inputs={"name": "John Doe"}),
    EntitySelectIndexStep(value=0),
    FormStep(children=[
        AnswerQuestionStep(question_text="Name", question_id="name", value="John Doe"),
        AnswerQuestionStep(question_text="Age", question_id="age", value="30"),
        SubmitFormStep(),
    ]),
])
