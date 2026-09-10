"""Typed AST for case search endpoint query builder filter specs.

A filter spec (the JSON the query builder produces) is parsed into a tree of
attrs nodes. :func:`parse_filter_spec` validates a spec against capability
metadata and, when valid, returns the typed tree a query builder can consume.

Endpoint parameters are shared by both kinds of endpoint. Project DB
endpoints additionally bind them into SQL: :func:`sql_placeholders` gives the
placeholder names a spec implies, and :func:`bind_values` maps a request's
search criteria onto the values those placeholders take.

The nodes follow the ``type``/``to_json``/``from_json`` convention used by
:mod:`corehq.apps.app_execution.data_model`, so they round-trip to and from
the stored JSON. (If a node tree is ever persisted via a model field, add
``__jsonattrs_to_json__``/``__jsonattrs_from_json__`` delegating to these.)
"""
from __future__ import annotations

from typing import ClassVar

from django.utils.translation import gettext as _

from attr import Factory, define, field as attr_field, validators

from corehq.apps.case_search.endpoint_capability import (
    FIELD_TYPE_DATERANGE,
    FIELD_TYPE_SELECT,
    INPUT_TYPE_CHOICE,
    INPUT_TYPE_MATCH_FIELD,
    OPERATORS,
    PARAMETER_TYPES,
)
from corehq.apps.case_search.exceptions import CaseSearchUserError

# Group node types: all = AND, any = OR, none = NOR (no child matches).
GROUP_TYPES = ('all', 'any', 'none')

# Maximum nesting depth of all/any/none groups.
MAX_QUERY_DEPTH = 5
# Maximum children per group.
MAX_GROUP_WIDTH = 50
# Maximum total nodes across the entire query tree.
MAX_TOTAL_NODES = 200

# How a date range criterion arrives: __range__YYYY-MM-DD__YYYY-MM-DD
DATE_RANGE_PREFIX = '__range__'

@define
class Parameter:
    name: str = attr_field(converter=str.strip, validator=validators.min_len(1))
    type: str = attr_field(validator=validators.in_(PARAMETER_TYPES))

def parse_parameter_spec(spec):
    """Validate a parameter list spec and parse it.

    :returns: a ``(parameters, errors)`` tuple. ``parameters`` is a list of
        :class:`Parameter` objects, or ``None`` when ``errors`` is non-empty.
    """
    errors = []
    if not isinstance(spec, list):
        return None, ['Parameters must be a JSON array.']

    parameters = []
    seen_names = set()
    for i, item in enumerate(spec, 1):
        if not isinstance(item, dict):
            errors.append(f'Parameter {i}: expected object, got {type(item).__name__}')
            continue

        item_errors = []
        name = item.get('name', '').strip()
        if not name or not isinstance(name, str):
            item_errors.append(f'Parameter {i}: name is required')
        elif name in seen_names:
            item_errors.append(f"Duplicate parameter name: '{name}'")
        else:
            seen_names.add(name)

        param_type = item.get('type', '')
        if param_type not in PARAMETER_TYPES:
            item_errors.append(
                f"Parameter '{name or i}': invalid type '{param_type}'."
                f" Must be one of: {', '.join(PARAMETER_TYPES)}"
            )

        if item_errors:
            errors.extend(item_errors)
        else:
            parameters.append(Parameter(name=name, type=param_type))

    errors.extend(_duplicate_placeholder_errors(parameters))
    if errors:
        return None, errors
    return parameters, []


def _duplicate_placeholder_errors(parameters):
    """A daterange derives two placeholder names, which may collide with
    another parameter's (``dob`` as a daterange and a ``dob_from`` text
    parameter both want ``:dob_from``)."""
    seen = set()
    for name in sql_placeholders(parameters):
        if name in seen:
            yield f"Duplicate SQL parameter name: '{name}'"
        seen.add(name)


def sql_placeholders(parameters):
    """The SQL placeholder names a parameter spec implies.

    A ``daterange`` parameter named ``dob`` is bound as ``:dob_from`` and
    ``:dob_to``; every other type is bound under its own name.
    """
    return [name for param in parameters for name in placeholders_for(param)]


def placeholders_for(param):
    """The SQL placeholder names a single parameter is bound to."""
    if param.type == FIELD_TYPE_DATERANGE:
        return [f'{param.name}_from', f'{param.name}_to']
    return [param.name]


def bind_values(parameters, criteria):
    """Map search criteria onto the values ``UserSQL.run`` expects.

    A criterion that is absent or blank binds as ``None``: NULL coerces to any
    column type, so endpoint SQL can guard every parameter with
    ``(:p IS NULL OR ...)``.

    :raises CaseSearchUserError: when a criterion's shape does not match the
        type its parameter declares.
    """
    by_key = {c.key: c for c in criteria}
    values = {}
    for param in parameters:
        values.update(_bind_parameter(param, by_key.get(param.name)))
    return values


def _bind_parameter(param, criterion):
    value = _value_without_blanks(criterion)
    if param.type == FIELD_TYPE_DATERANGE:
        return dict(zip(placeholders_for(param), _as_date_range(param, value)))
    if param.type == FIELD_TYPE_SELECT:
        return {param.name: _as_list(value)}
    return {param.name: _as_scalar(param, value)}


def _value_without_blanks(criterion):
    """The criterion's value, with blank terms dropped and blank read as unset"""
    if criterion is None:
        return None
    if criterion.has_multiple_terms:
        # A single remaining term is flattened back to a scalar
        return criterion.clone_without_blanks().value or None
    return criterion.value or None


def _as_scalar(param, value):
    if isinstance(value, list):
        raise CaseSearchUserError(
            _("Only one value may be given for '{}'").format(param.name)
        )
    return value


def _as_list(value):
    """Bound as a list whatever the number of values, so that endpoint SQL
    comparing against an array column works no matter what was searched for."""
    if value is None:
        return None
    return value if isinstance(value, list) else [value]


def _as_date_range(param, value):
    if value is None:
        return None, None
    if isinstance(value, list) or not str(value).startswith(DATE_RANGE_PREFIX):
        raise CaseSearchUserError(
            _("'{}' must be given as a date range").format(param.name)
        )
    start, _sep, end = str(value).removeprefix(DATE_RANGE_PREFIX).partition('__')
    if not start or not end:
        raise CaseSearchUserError(
            _("Invalid date range for '{}'").format(param.name)
        )
    return start, end

@define
class ConstantInput:
    """A literal input value supplied directly in the spec."""

    type: ClassVar[str] = 'constant'
    value: object = None

    def to_json(self):
        return {'type': self.type, 'value': self.value}

    @classmethod
    def from_json(cls, data):
        return cls(value=data.get('value'))

@define
class ParameterInput:
    """An input value supplied by referencing a named parameter."""

    type: ClassVar[str] = 'parameter'
    value: str = attr_field(converter=str.strip, validator=validators.min_len(1))

    def to_json(self):
        return {'type': self.type, 'value': self.value}

    @classmethod
    def from_json(cls, data):
        return cls(value=data.get('value'))

# input type -> class. Add parameter/function input kinds here.
INPUT_TYPES = {
    ConstantInput.type: ConstantInput,
    ParameterInput.type: ParameterInput,
}

def input_from_json(data):
    input_type = data.get('type')
    if input_type not in INPUT_TYPES:
        raise ValueError(f"Unknown input type: {input_type!r}")
    return INPUT_TYPES[input_type].from_json(data)

@define
class ComponentNode:
    """A leaf condition: an operation applied to a field with its inputs."""

    type: ClassVar[str] = 'component'
    operator: str = attr_field(validator=validators.in_(OPERATORS))
    inputs: dict = Factory(dict)  # slot name -> input object
    field: str = ''
    field_type: str = ''  # resolved from capability at parse time

    def to_json(self):
        return {
            'type': self.type,
            'field': self.field,
            'operator': self.operator,
            'inputs': {
                name: inp.to_json() for name, inp in self.inputs.items()
            },
        }

    @classmethod
    def from_json(cls, data, fields_by_name=None):
        field_name = data.get('field', '')
        field_type = ''
        if fields_by_name and field_name in fields_by_name:
            field_type = fields_by_name[field_name]['type']
        return cls(
            field=field_name,
            operator=data.get('operator', ''),
            inputs={
                name: input_from_json(value)
                for name, value in (data.get('inputs') or {}).items()
            },
            field_type=field_type,
        )


@define
class GroupNode:
    """A boolean group combining child nodes with all/any/none."""

    type: str = attr_field(validator=validators.in_(GROUP_TYPES))
    children: list = Factory(list)  # list[GroupNode | ComponentNode]

    def to_json(self):
        return {
            'type': self.type,
            'children': [child.to_json() for child in self.children],
        }

    @classmethod
    def from_json(cls, data, fields_by_name=None):
        return cls(
            type=data['type'],
            children=[node_from_json(c, fields_by_name) for c in data.get('children', [])],
        )


def node_from_json(data, fields_by_name=None):
    """Build a node tree from a raw spec dict."""
    node_type = data.get('type')
    if node_type in GROUP_TYPES:
        return GroupNode.from_json(data, fields_by_name)
    if node_type == ComponentNode.type:
        return ComponentNode.from_json(data, fields_by_name)
    raise ValueError(f'Unknown node type: {node_type!r}')


def parse_query_spec(query_spec, parameters, case_type_name, capability):
    """Validate a query spec against capability metadata and parse it.

    :returns: a ``(root, errors)`` tuple. ``root`` is the parsed node tree (an
        attrs ``GroupNode``/``ComponentNode``), or ``None`` when ``errors`` (a
        list of message strings) is non-empty.
    """
    errors = []
    fields_by_name = _fields_by_name(capability, case_type_name, errors)
    if errors:
        return None, errors

    try:
        root = node_from_json(query_spec, fields_by_name)
    except (TypeError, ValueError, KeyError, AttributeError):
        return None, ['Invalid query']

    _check_structural_limits(root, errors)
    if not errors:
        _check_semantics(
            root, fields_by_name, parameters,
            capability.get('operator_input_schemas', {}), errors,
        )
    if errors:
        return None, errors
    return root, []


def _fields_by_name(capability, case_type_name, errors):
    case_types = capability.get('case_types', {})
    if case_type_name not in case_types:
        errors.append(f"Unknown case type: '{case_type_name}'")
        return {}
    return case_types[case_type_name]


def _check_structural_limits(node, errors, depth=0, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > MAX_TOTAL_NODES:
        errors.append(f'Query has too many nodes (max {MAX_TOTAL_NODES})')
        return
    if depth > MAX_QUERY_DEPTH:
        errors.append(f'Query is nested too deeply (max {MAX_QUERY_DEPTH} levels)')
        return
    if isinstance(node, GroupNode):
        if len(node.children) > MAX_GROUP_WIDTH:
            errors.append(f'Group has too many conditions (max {MAX_GROUP_WIDTH})')
            return
        for child in node.children:
            _check_structural_limits(child, errors, depth + 1, counter)


def _check_semantics(node, fields_by_name, parameters, operator_input_schemas, errors):
    if isinstance(node, GroupNode):
        for child in node.children:
            _check_semantics(child, fields_by_name, parameters, operator_input_schemas, errors)
    elif isinstance(node, ComponentNode):
        _check_component(node, fields_by_name, parameters, operator_input_schemas, errors)


def _check_component(node, fields_by_name, parameters, operator_input_schemas, errors):
    field = fields_by_name.get(node.field)
    if not field:
        errors.append(f"Unknown field: '{node.field}'")
        return

    operation_names = [op['name'] for op in field.get('operations', [])]
    if node.operator not in operation_names:
        errors.append(
            f"'{node.operator}' is not a valid operation for field "
            f"'{node.field}' (type: {field['type']})"
        )
        return

    field_type = field['type']
    resolved_slots = {
        slot['name']: field_type if slot['type'] == INPUT_TYPE_MATCH_FIELD else slot['type']
        for slot in operator_input_schemas.get(node.operator, [])
    }

    for slot in operator_input_schemas.get(node.operator, []):
        slot_name = slot['name']
        if slot_name not in node.inputs:
            errors.append(
                f"Missing required input '{slot_name}' for component '{node.operator}'"
            )
            continue
        inp = node.inputs[slot_name]
        if slot['type'] == INPUT_TYPE_CHOICE:
            _check_choice_input(inp, slot, slot_name, errors)
        elif isinstance(inp, ParameterInput):
            _check_parameter_input(inp, parameters, slot_name, resolved_slots[slot_name], errors)


def _check_choice_input(inp, slot, slot_name, errors):
    if not isinstance(inp, ConstantInput):
        errors.append(f"Input '{slot_name}' must be a fixed value, not a parameter")
        return
    options = slot.get('options', [])
    if inp.value not in options:
        errors.append(
            f"Input '{slot_name}': '{inp.value}' is not a valid option."
            f" Must be one of: {', '.join(options)}"
        )


def _check_parameter_input(inp, parameters, slot_name, slot_type, errors):
    referenced = next((p for p in parameters if p.name == inp.value), None)
    if not referenced:
        errors.append(f"Input '{slot_name}': parameter {inp.value} not configured")
    elif referenced.type != slot_type:
        errors.append(
            f"Input '{slot_name}': parameter '{inp.value}' has type "
            f"'{referenced.type}', expected '{slot_type}'"
        )
