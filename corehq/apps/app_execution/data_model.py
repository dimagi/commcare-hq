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


@dataclasses.dataclass
class Workflow:
    steps: list[Step] = dataclasses.field(default_factory=list)

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

    def __str__(self):
        return f"Command: {self.value}"


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
            "idx": question["ix"],
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
            "answers": answers
        }


@dataclasses.dataclass
class FormStep(Step):
    type: ClassVar[str] = "form"
    children: list[AnswerQuestionStep | SubmitFormStep]

    def get_children(self):
        return self.children


def _append_selection(data, selection):
    selections = data.get("selections", [])
    selections.append(selection)
    return {**data, "selections": selections}
