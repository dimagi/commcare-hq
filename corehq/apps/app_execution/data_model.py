from __future__ import annotations

import dataclasses
from typing import ClassVar


@dataclasses.dataclass
class Step:
    type: ClassVar[str]

    def get_request_data(self, session, data):
        return data

    def get_children(self):
        return []

    def to_dict(self):
        return {"type": self.type, **dataclasses.asdict(self)}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclasses.dataclass
class Workflow:
    steps: list[Step] = dataclasses.field(default_factory=list)

    def to_dict(self):
        return {
            "steps": [step.to_dict() for step in self.steps]
        }

    @classmethod
    def from_dict(cls, data):
        workflow = cls()
        for step in data["steps"]:
            step_type = step.pop("type")
            step_class = STEP_MAP[step_type]
            workflow.steps.append(step_class.from_dict(step))
        return workflow

    def __str__(self):
        return " -> ".join(str(step) for step in self.steps)


@dataclasses.dataclass
class CommandStep(Step):
    type: ClassVar[str] = "command"
    value: str

    def get_request_data(self, session, data):
        commands = {c["displayText"].lower(): c for c in session.data.get("commands", [])}

        try:
            command = commands[self.value.lower()]
        except KeyError:
            raise ValueError(f"Command not found: {self.value}: {commands.keys()}")
        return _append_selection(data, command["index"])


@dataclasses.dataclass
class EntitySelectStep(Step):
    type: ClassVar[str] = "entity_select"
    value: str

    def get_request_data(self, session, data):
        entities = {entity["id"] for entity in session.data.get("entities", [])}
        if self.value not in entities:
            raise ValueError(f"Entity not found: {self.value}")
        return _append_selection(data, self.value)

    def __str__(self):
        return f"Entity Select: {self.value}"


@dataclasses.dataclass
class QueryStep(Step):
    type: ClassVar[str] = "query"
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


@dataclasses.dataclass
class AnswerQuestionStep(Step):
    type: ClassVar[str] = "answer_question"
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
            raise ValueError(f"Question not found: {self.question_text or self.question_id}")

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


@dataclasses.dataclass
class SubmitFormStep(Step):
    type: ClassVar[str] = "submit_form"

    def get_request_data(self, session, data):
        answers = {
            node["ix"]: node["answer"] or "OK"
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


@dataclasses.dataclass
class FormStep(Step):
    type: ClassVar[str] = "form"
    children: list[AnswerQuestionStep | SubmitFormStep]

    def to_dict(self):
        return {
            "type": self.type,
            "children": [child.to_dict() for child in self.children]
        }

    def get_children(self):
        return self.children

    @classmethod
    def from_dict(cls, data):
        return cls(children=[STEP_MAP[child.pop("type")].from_dict(child) for child in data["children"]])


def _append_selection(data, selection):
    selections = data.get("selections", [])
    selections.append(selection)
    return {**data, "selections": selections}


STEP_MAP = {
    "command": CommandStep,
    "entity_select": EntitySelectStep,
    "query": QueryStep,
    "answer_question": AnswerQuestionStep,
    "submit_form": SubmitFormStep,
    "form": FormStep,
}
