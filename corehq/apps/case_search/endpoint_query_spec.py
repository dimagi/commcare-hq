"""Typed AST for case search endpoint query builder filter specs.

A filter spec (the JSON the query builder produces) is parsed into a tree of
attrs nodes. :func:`parse_filter_spec` validates a spec against capability
metadata and, when valid, returns the typed tree a query builder can consume.

The nodes follow the ``type``/``to_json``/``from_json`` convention used by
:mod:`corehq.apps.app_execution.data_model`, so they round-trip to and from
the stored JSON. (If a node tree is ever persisted via a model field, add
``__jsonattrs_to_json__``/``__jsonattrs_from_json__`` delegating to these.)
"""
from __future__ import annotations

from typing import ClassVar

from attr import Factory, define, field as attr_field, validators

from corehq.apps.case_search.endpoint_capability import FIELD_TYPES, INPUT_TYPE_MATCH_FIELD, OPERATORS

# Group node types: all = AND, any = OR, none = NOR (no child matches).
GROUP_TYPES = ('all', 'any', 'none')

# Maximum nesting depth of all/any/none groups.
MAX_QUERY_DEPTH = 5
# Maximum children per group.
MAX_GROUP_WIDTH = 50
# Maximum total nodes across the entire query tree.
MAX_TOTAL_NODES = 200

@define
class Parameter:
    name: str = attr_field(converter=str.strip, validator=validators.min_len(1))
    type: str = attr_field(validator=validators.in_(FIELD_TYPES))

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
        if param_type not in FIELD_TYPES:
            item_errors.append(
                f"Parameter '{name or i}': invalid type '{param_type}'."
                f" Must be one of: {', '.join(FIELD_TYPES)}"
            )

        if item_errors:
            errors.extend(item_errors)
        else:
            parameters.append(Parameter(name=name, type=param_type))

    if errors:
        return None, errors
    return parameters, []

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
        if isinstance(inp, ParameterInput):
            _check_parameter_input(inp, parameters, slot_name, resolved_slots[slot_name], errors)


def _check_parameter_input(inp, parameters, slot_name, slot_type, errors):
    referenced = next((p for p in parameters if p.name == inp.value), None)
    if not referenced:
        errors.append(f"Input '{slot_name}': parameter {inp.value} not configured")
    elif referenced.type != slot_type:
        errors.append(
            f"Input '{slot_name}': parameter '{inp.value}' has type "
            f"'{referenced.type}', expected '{slot_type}'"
        )
