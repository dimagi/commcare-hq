from __future__ import annotations

import copy
from typing import Any, ClassVar

from attr import Factory, define
from attrs import asdict

from ..exceptions import AppExecutionError


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
class CommandStep(Step):
    type: ClassVar[str] = "command"
    is_form_step: ClassVar[bool] = False

    value: str = ""
    """Display text of the command to execute"""

    def get_request_data(self, session, data):
        commands = {c["displayText"].lower(): c for c in session.data.get("commands", [])}

        try:
            command = commands[self.value.lower()]
        except KeyError:
            raise AppExecutionError(f"Command not found: {self.value}: {commands.keys()}")
        return _append_selection(data, command["index"])


@define
class CommandIdStep(Step):
    type: ClassVar[str] = "command_id"
    is_form_step: ClassVar[bool] = False

    value: str = ""
    """ID of the command to execute"""

    def get_request_data(self, session, data):
        return _append_selection(data, self.value)


@define
class EntitySelectStep(Step):
    type: ClassVar[str] = "entity_select"
    is_form_step: ClassVar[bool] = False

    value: str
    """ID of the entity to select."""

    def get_request_data(self, session, data):
        _validate_entity_ids(session, [self.value])
        return _append_selection(data, self.value)

    def __str__(self):
        return f"Entity Select: {self.value}"


@define
class MultipleEntitySelectStep(Step):
    type: ClassVar[str] = "multiple_entity_select"
    is_form_step: ClassVar[bool] = False

    values: list[str]

    def get_request_data(self, session, data):
        _validate_entity_ids(session, self.values)
        data = _append_selection(data, "use_selected_values")
        data["selectedValues"] = self.values
        return data


def _validate_entity_ids(session, entity_ids):
    entities = {entity["id"] for entity in session.data.get("entities", [])}
    if not entities:
        raise AppExecutionError("No entities found")
    missing = set(entity_ids) - entities
    if missing:
        raise AppExecutionError(f"Entities not found: {missing}: {list(entities)}")


@define
class EntitySelectIndexStep(Step):
    type: ClassVar[str] = "entity_select_index"
    is_form_step: ClassVar[bool] = False

    value: int
    """Zero-based index of the entity to select."""

    def get_request_data(self, session, data):
        selected = _select_entities_by_index(session, [self.value])
        return _append_selection(data, selected[0])

    def __str__(self):
        return f"Entity Select: {self.value}"


@define
class MultipleEntitySelectByIndexStep(Step):
    type: ClassVar[str] = "multiple_entity_select_by_index"
    is_form_step: ClassVar[bool] = False

    values: list[int]

    def get_request_data(self, session, data):
        selected = _select_entities_by_index(session, self.values)
        data = _append_selection(data, "use_selected_values")
        data["selectedValues"] = selected
        return data


def _select_entities_by_index(session, indexes):
    entities = [entity["id"] for entity in session.data.get("entities", [])]
    if not entities:
        raise AppExecutionError("No entities found")
    if max(indexes) >= len(entities):
        raise AppExecutionError(f"Entity index out of range: {max(indexes)}: {list(entities)}")
    return [entities[index] for index in indexes]


@define
class QueryInputValidationStep(Step):
    type: ClassVar[str] = "query_input_validation"
    is_form_step: ClassVar[bool] = False

    inputs: dict
    """Search inputs dict. Keys are field names and values are search values."""

    def get_request_data(self, session, data):
        query_key = session.data["queryKey"]
        return {
            **data,
            # DataDog tag value
            "requestInitiatedByTag": "field_change",
            "query_data": {
                query_key: {
                    "execute": False,
                    "force_manual_search": True,
                    "inputs": self.inputs,
                }
            },
        }


@define
class QueryStep(Step):
    type: ClassVar[str] = "query"
    is_form_step: ClassVar[bool] = False

    inputs: dict
    """Search inputs dict. Keys are field names and values are search values."""

    validate_inputs: bool = False
    """Simulate updating search inputs on the UI. One request per update."""

    def get_children(self):
        children = []
        if self.validate_inputs:
            # children will be executed instead of the parent
            inputs = {}
            for field, value in self.inputs.items():
                inputs[field] = value
                children.append(QueryInputValidationStep(inputs=inputs.copy()))
            children.append(QueryStep(inputs=self.inputs))  # execute query
        return children

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
class ClearQueryStep(Step):
    """This is implemented in the suite file with `redo_last="true"` and appears on the UI
    as "Search Again"
    """
    type: ClassVar[str] = "clear_query"
    is_form_step: ClassVar[bool] = False

    def get_request_data(self, session, data):
        query_key = session.data["queryKey"]
        return {
            **data,
            "query_data": {
                query_key: {
                    "inputs": None,
                    "execute": False,
                    "force_manual_search": True,
                }
            },
        }

    def __str__(self):
        return "ClearQuery"


@define
class AnswerQuestionStep(Step):
    type: ClassVar[str] = "answer_question"
    is_form_step: ClassVar[bool] = True
    question_text: str
    value: str

    @classmethod
    def from_json(cls, data):
        data.pop("question_id", None)
        return cls(**data)

    def get_request_data(self, session, data):
        return {
            **data,
            **_get_answer_data(session, "caption", self.question_text, self.value)
        }

    def __str__(self):
        return f"Answer Question: {self.question_text} = {self.value}"


@define
class AnswerQuestionIdStep(Step):
    type: ClassVar[str] = "answer_question_id"
    is_form_step: ClassVar[bool] = True
    question_id: str
    value: str

    def get_request_data(self, session, data):
        return {
            **data,
            **_get_answer_data(session, "question_id", self.question_id, self.value)
        }

    def __str__(self):
        return f"Answer Question: {self.question_id} = {self.value}"


def _get_answer_data(session, node_field_name, node_value, answer):
    try:
        question = [
            node for node in session.data["tree"]
            if node[node_field_name] == node_value
        ][0]
    except IndexError:
        raise AppExecutionError(f"Question not found: {node_value}")

    return {
        "action": "answer",
        "answersToValidate": {},
        "answer": answer,
        "ix": question["ix"],
        "session_id": session.data["session_id"]
    }


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
    is_form_step: ClassVar[bool] = False  # the children are all form steps but this one isn't
    children: list[Any] = Factory(list)

    def to_json(self):
        return {
            "type": self.type,
            "children": [child.to_json() for child in self.children]
        }

    def get_children(self):
        return self.children

    @classmethod
    def from_json(cls, data):
        from .base import steps_from_json
        return cls(children=steps_from_json(data["children"]))


@define
class RawNavigationStep(Step):
    type: ClassVar[str] = "raw_navigation"
    is_form_step: ClassVar[bool] = False

    request_data: dict

    def get_request_data(self, session, data):
        return self.request_data


def _append_selection(data, selection):
    selections = data.get("selections", [])
    selections.append(selection)
    return {**data, "selections": selections}


STEP_MAP = {step.type: step for step in Step.__subclasses__()}


def steps_from_json(raw_steps):
    raw_steps = copy.deepcopy(raw_steps)
    return [STEP_MAP[child.pop("type")].from_json(child) for child in raw_steps]
