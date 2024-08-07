import dataclasses
import json
import re
from operator import attrgetter
from typing import Any, Callable

from corehq.apps.app_execution import data_model
from corehq.apps.app_execution.exceptions import AppExecutionError


def dsl_to_workflow(dsl_str):
    """Parse a DSL string into an AppWorkflow object
    Rules:
    - Lines starting with '#' are ignored
    - Blank lines are ignored
    - Line indentation is ignored
    - All other lines must map to a workflow step
    """
    lines = dsl_str.splitlines()
    steps = []
    nested = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if nested and nested[-1].match_end(line):
            nested.pop()
            continue

        step, dsl = _line_to_step(line)
        if nested:
            steps[-1].children.append(step)
        else:
            steps.append(step)

        if isinstance(dsl, NestedDsl):
            nested.append(dsl)

    return data_model.AppWorkflow(steps=steps)


def _line_to_step(line):
    for dsl in DSL:
        try:
            step = dsl.from_dsl(line)
        except Exception as e:
            raise AppExecutionError(f"Error parsing line '{line}': {e}")

        if not step:
            # try next parser
            continue

        return step, dsl

    raise AppExecutionError(f"Invalid step: {line}")


def workflow_to_dsl(workflow):
    """Convert an AppWorkflow object into a DSL string"""
    lines = _steps_to_dsl_lines(workflow.steps)
    return '\n'.join(lines)


def _steps_to_dsl_lines(steps, depth=0):
    lines = []
    for step in steps:
        dsl = DSL_MAP.get(step.type)
        if not dsl:
            raise AppExecutionError(f"Unsupported step type: {step.type}")
        indent = "  " * depth
        dsl_out = dsl.to_dsl(step)
        if isinstance(dsl_out, list):
            lines.extend([indent + line for line in dsl_out])
        else:
            lines.append(indent + dsl_out)
    return lines


def identity(x):
    """Identity function"""
    return x


@dataclasses.dataclass
class SimpleDsl:
    """DSL class that maps a step class to a DSL format string and regex parser

    By default, the step is assumed to have a `value` attribute which is passed to the
    format string unchanged.

    The line regex should use named groups to extract values from the line which are passed
    to the Step constructor as keyword arguments.
    """
    step_cls: type[Any]
    format_str: str
    parse_regex: str
    value_to_str: Callable[[Any], str] = attrgetter('value')
    dict_to_kwargs: Callable[[dict], dict] = identity

    def to_dsl(self, step):
        return self.format_str.format(step=step, value=self.value_to_str(step))

    def from_dsl(self, line):
        if match := re.match(self.parse_regex, line, re.IGNORECASE):
            return self.step_cls(**self.dict_to_kwargs(match.groupdict()))


@dataclasses.dataclass
class NestedDsl:
    step_cls: type[Any]
    starting: str
    ending: str

    def to_dsl(self, step):
        dsl = [self.starting.format(step=step)]
        dsl.extend(_steps_to_dsl_lines(step.get_children(), depth=1))
        dsl.append(self.ending.format(step=step))
        return dsl

    def from_dsl(self, line):
        if re.match(self.starting, line, re.IGNORECASE):
            return self.step_cls()

    def match_end(self, line):
        return re.match(self.ending, line, re.IGNORECASE)


def _format_kv_pairs(field_name):
    """Factory function to produce a CSV string formatter for a field in a step class.

    Inverse of `_get_key_value_pairs`
    """

    def _formatter(step):
        return ", ".join(f'{k}="{v}"' for k, v in getattr(step, field_name).items())

    return _formatter


def _get_key_value_pairs(line):
    """Extract key-value pairs from a string in the format 'key="value", key2="value2"'
    and return them as a dict.

    Inverse of `_format_kv_pairs`
    """
    inputs = {}
    for match in re.finditer(r'([\w-]+)="(.+?)"', line):
        inputs[match.group(1)] = match.group(2)
    return inputs


@dataclasses.dataclass
class KeyValueDsl(SimpleDsl):
    """DSL class for steps that contain key-value pairs i.e. a dictionary of inputs
    """

    field_name: str = "inputs"
    """The name of the dict field in the step class"""

    def to_dsl(self, step):
        self.value_to_str = _format_kv_pairs(self.field_name)
        return super().to_dsl(step)

    def from_dsl(self, line):
        if re.match(self.parse_regex, line, re.IGNORECASE):
            return self.step_cls(inputs=_get_key_value_pairs(line))


def join_values(field_name):
    """Factory function to produce a CSV string joiner for a field in a step class.
    Inverse of `split_values`

    Args:
        field_name (str): The name of the field in the step class
    """

    def _joiner(step):
        value = getattr(step, field_name)
        return ', '.join(map(str, value))

    return _joiner


def split_values(field_name, groupdict_field='value', cast=str):
    """Factory function to produce a value splitter for a regex groupdict.
    Inverse of `join_values`

    Args:
        field_name (str): The name of the field in the step class
        groupdict_field (str): The name of the field in the regex match groupdict
        cast (callable): A function to cast the value to the desired type
    """

    def _splitter(groupdict):
        values = []
        for val in groupdict[groupdict_field].split(','):
            if val_clean := val.strip():
                try:
                    values.append(cast(val_clean))
                except Exception:
                    raise AppExecutionError(f"Invalid value: {val_clean}")
        return {field_name: values}

    return _splitter


def cast_value(field_name, cast):
    """Factory function to produce a value caster for a regex groupdict.

    Args:
        cast (callable): A function to cast the value to the desired type
    """

    def _caster(groupdict):
        return {field_name: cast(groupdict[field_name])}

    return _caster


VALUE_ENDING = r'\s+"(?P<value>.*?)"$'

DSL = [
    SimpleDsl(
        data_model.steps.CommandStep,
        'Select menu "{value}"',
        fr'^Select menu{VALUE_ENDING}'
    ),
    SimpleDsl(
        data_model.steps.CommandIdStep,
        'Select menu with ID "{value}"',
        fr'^Select menu with ID{VALUE_ENDING}'
    ),
    SimpleDsl(
        data_model.steps.EntitySelectStep,
        'Select entity with ID "{value}"',
        fr'^select entity with id{VALUE_ENDING}'
    ),
    SimpleDsl(
        data_model.steps.MultipleEntitySelectStep,
        'Select entities with IDs "{value}"',
        fr'^Select entities with IDs{VALUE_ENDING}',
        value_to_str=join_values("values"),
        dict_to_kwargs=split_values("values")
    ),
    SimpleDsl(
        data_model.steps.EntitySelectIndexStep,
        'Select entity at index {value}',
        r'^select entity at index\s+(?P<value>\d+)$',
        dict_to_kwargs=cast_value("value", int)
    ),
    SimpleDsl(
        data_model.steps.MultipleEntitySelectByIndexStep,
        'Select entities at indexes {value}',
        r'^Select entities at indexes\s+(?P<values>[\d,\s]+)$',
        value_to_str=join_values("values"),
        dict_to_kwargs=split_values("values", groupdict_field="values", cast=int)
    ),
    KeyValueDsl(
        data_model.steps.QueryInputValidationStep,
        'Update search parameters {value}',
        r'^Update search parameters',
        field_name="inputs",
    ),
    KeyValueDsl(
        data_model.steps.QueryStep,
        'Search with parameters {value}',
        r'^Search with parameters',
        field_name="inputs",
    ),
    SimpleDsl(
        data_model.steps.ClearQueryStep,
        'Clear search',
        r'^clear search$',
        value_to_str=identity
    ),
    SimpleDsl(
        data_model.steps.AnswerQuestionStep,
        'Answer question "{step.question_text}" with "{value}"',
        fr'^Answer question\s+"(?P<question_text>.+?)"\s+with{VALUE_ENDING}'
    ),
    SimpleDsl(
        data_model.steps.AnswerQuestionIdStep,
        'Answer question with ID "{step.question_id}" with "{value}"',
        fr'^Answer question with ID\s+"(?P<question_id>.+?)"\s+with{VALUE_ENDING}'
    ),
    SimpleDsl(
        data_model.steps.SubmitFormStep,
        'Submit form',
        r'^submit form$',
        value_to_str=identity,
    ),
    SimpleDsl(
        data_model.steps.RawNavigationStep,
        'Raw navigation request data {value}',
        r'^Raw navigation request data\s+(?P<value>.*)$',
        value_to_str=lambda step: json.dumps(step.request_data),
        dict_to_kwargs=lambda groupdict: {"request_data": json.loads(groupdict["value"])},
    ),
    NestedDsl(
        data_model.steps.FormStep,
        starting='Start form',
        ending="End form"
    ),

    # Expectations
    SimpleDsl(
        data_model.expectations.XpathExpectation,
        'Expect xpath {value}',
        r'^Expect xpath\s+(?P<xpath>.+)$',
        value_to_str=attrgetter('xpath'),
    ),
    SimpleDsl(
        data_model.expectations.CasePresent,
        'Expect case present {value}',
        r'^Expect case present\s+(?P<xpath_filter>.+)$',
        value_to_str=attrgetter('xpath_filter'),
    ),
    SimpleDsl(
        data_model.expectations.CaseAbsent,
        'Expect case absent {value}',
        r'^Expect case absent\s+(?P<xpath_filter>.+)$',
        value_to_str=attrgetter('xpath_filter'),
    ),
    SimpleDsl(
        data_model.expectations.QuestionValue,
        'Expect question "{step.question_path}" with "{value}"',
        rf'^Expect question\s+"(?P<question_path>.+?)"\s+with{VALUE_ENDING}',
    ),
]

DSL_MAP = {dsl.step_cls.type: dsl for dsl in DSL}
