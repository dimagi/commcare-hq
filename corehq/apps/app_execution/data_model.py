from __future__ import annotations

import copy
import dataclasses
import re
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

    def to_dsl(self):
        raise NotImplementedError

    @classmethod
    def from_dsl(cls, line):
        raise NotImplementedError(cls.__name__)


@define
class AppWorkflow:
    steps: list[Step] = dataclasses.field(default_factory=list)

    def to_dsl(self):
        return "\n".join(step.to_dsl() for step in self.steps)

    @classmethod
    def from_dsl(cls, dsl_str):
        lines = dsl_str.splitlines()
        steps = []
        for line in lines:
            for step_cls in STEP_MAP.values():
                if step := step_cls.from_dsl(line):
                    if step.is_form_step:
                        if not isinstance(steps[-1], FormStep):
                            steps.append(FormStep(children=[]))
                        steps[-1].children.append(step)
                    else:
                        steps.append(step)
                    break
            else:
                raise AppExecutionError(f"Invalid step: {line}")
        return AppWorkflow(steps=steps)

    def to_json(self):
        return self.__jsonattrs_to_json__()

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

    value: str = ""
    """Display text of the command to execute"""

    id: str = ""
    """ID of the command to execute"""

    @classmethod
    def from_dsl(cls, line):
        if match := re.match(r'select menu with id\s+"(.+)"', line, re.IGNORECASE):
            return cls(id=match.group(1))
        elif match := re.match(r'select menu\s+"(.+)"', line, re.IGNORECASE):
            return cls(value=match.group(1))

    def to_dsl(self):
        if self.value:
            return f'Select menu "{self.value}"'
        if self.id:
            return f'Select menu with ID "{self.id}"'

    def to_json(self):
        data = super().to_json()
        for key in ["value", "id"]:
            if not getattr(self, key):
                data.pop(key)
        return data

    @classmethod
    def from_json(cls, data):
        data.pop("selected_values", None)  # remove legacy field
        return cls(**data)

    def get_request_data(self, session, data):
        if self.id:
            return _append_selection(data, self.id)

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
    """ID of the entity to select."""

    @classmethod
    def from_dsl(cls, line):
        if match := re.match(r'select entity with id\s+"(.+)"', line, re.IGNORECASE):
            return cls(value=match.group(1))

    def to_dsl(self):
        return f'Select entity with ID "{self.value}"'

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

    @classmethod
    def from_dsl(cls, line):
        if match := re.match(r'select entities with ids\s+"(.+)"', line, re.IGNORECASE):
            ids = [id_.strip() for id_ in match.group(1).split(",")]
            return cls(values=ids)

    def to_dsl(self):
        return f'Select entities with IDs "{", ".join(self.values)}"'

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

    @classmethod
    def from_dsl(cls, line):
        if match := re.match(r'select entity at index\s+(\d+)', line, re.IGNORECASE):
            return cls(value=int(match.group(1)))

    def to_dsl(self):
        return f'Select entity at index {self.value}'

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

    @classmethod
    def from_dsl(cls, line):
        if match := re.match(r'select entities at indexes\s+"([\d,\s]+)"', line, re.IGNORECASE):
            ids = [int(id_.strip()) for id_ in match.group(1).split(",")]
            return cls(values=ids)

    def to_dsl(self):
        return f'Select entities at indexes "{", ".join(map(str, self.values))}"'

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

    @classmethod
    def from_dsl(cls, line):
        if re.match(r'update search parameters', line, re.IGNORECASE):
            return cls(inputs=_get_key_value_pairs(line))

    def to_dsl(self):
        params = ", ".join(f'{k}="{v}"' for k, v in self.inputs.items())
        return f'Update search parameters {params}'

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


def _get_key_value_pairs(line):
    inputs = {}
    for match in re.finditer(r'([\w-]+)="(.+?)"', line):
        inputs[match.group(1)] = match.group(2)
    return inputs


@define
class QueryStep(Step):
    type: ClassVar[str] = "query"
    is_form_step: ClassVar[bool] = False

    inputs: dict
    """Search inputs dict. Keys are field names and values are search values."""

    validate_inputs: bool = False
    """Simulate updating search inputs on the UI. One request per update."""

    @classmethod
    def from_dsl(cls, line):
        if re.match(r'search with parameters', line, re.IGNORECASE):
            return cls(inputs=_get_key_value_pairs(line))

    def to_dsl(self):
        params = ", ".join(f'{k}="{v}"' for k, v in self.inputs.items())
        return f'Search with parameters {params}'

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

    @classmethod
    def from_dsl(cls, line):
        if re.match(r'clear search', line, re.IGNORECASE):
            return cls()

    def to_dsl(self):
        return "Clear search"

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
    value: str
    question_text: str = None
    question_id: str = None

    @classmethod
    def from_dsl(cls, line):
        if match := re.match(r'answer question "(.+?)" with "(.+?)"', line, re.IGNORECASE):
            return cls(question_text=match.group(1), value=match.group(2))
        elif match := re.match(r'answer question with id "(.+?)" with "(.+?)"', line, re.IGNORECASE):
            return cls(question_id=match.group(1), value=match.group(2))

    def to_dsl(self):
        if self.question_text:
            return f'Answer question "{self.question_text}" with "{self.value}"'
        if self.question_id:
            return f'Answer question with ID "{self.question_id}" with "{self.value}"'

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

    @classmethod
    def from_dsl(cls, line):
        if re.match(r'submit form', line, re.IGNORECASE):
            return cls()

    def to_dsl(self):
        return "Submit form"

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
    is_form_step: ClassVar[bool] = True
    children: list[AnswerQuestionStep | SubmitFormStep]

    @classmethod
    def from_dsl(cls, line):
        return None

    def to_dsl(self):
        return "\n".join(child.to_dsl() for child in self.children)

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


@define
class RawNavigationStep(Step):
    type: ClassVar[str] = "raw_navigation"
    is_form_step: ClassVar[bool] = False

    request_data: dict

    @classmethod
    def from_dsl(cls, line):
        if re.match(r'navigate using raw request data', line, re.IGNORECASE):
            raise AppExecutionError("Raw navigation step not supported in DSL")

    def to_dsl(self):
        return "Navigate using raw request data"

    def get_request_data(self, session, data):
        return self.request_data


def _append_selection(data, selection):
    selections = data.get("selections", [])
    selections.append(selection)
    return {**data, "selections": selections}


STEP_MAP = {step.type: step for step in Step.__subclasses__()}


def _steps_from_json(data):
    data = copy.deepcopy(data)
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
