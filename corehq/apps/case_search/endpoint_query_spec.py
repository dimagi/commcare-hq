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

from attr import Factory, define, field, validators

# Group node types: all = AND, any = OR, none = NOR (no child matches).
GROUP_TYPES = ('all', 'any', 'none')

# Maximum nesting depth of all/any/none groups.
MAX_QUERY_DEPTH = 5
# Maximum children per group.
MAX_GROUP_WIDTH = 50
# Maximum total nodes across the entire query tree.
MAX_TOTAL_NODES = 200


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


# input type -> class. Add parameter/function input kinds here.
INPUT_TYPES = {ConstantInput.type: ConstantInput}


def input_from_json(data):
    input_type = data.get('type')
    if input_type not in INPUT_TYPES:
        raise ValueError(f"Unknown input type: {input_type!r}")
    return INPUT_TYPES[input_type].from_json(data)


@define
class ComponentNode:
    """A leaf condition: an operation applied to a field with its inputs."""

    type: ClassVar[str] = 'component'
    field: str = ''
    operator: str = ''
    inputs: dict = Factory(dict)  # slot name -> input object

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
    def from_json(cls, data):
        return cls(
            field=data.get('field', ''),
            operator=data.get('operator', ''),
            inputs={
                name: input_from_json(value)
                for name, value in (data.get('inputs') or {}).items()
            },
        )


@define
class GroupNode:
    """A boolean group combining child nodes with all/any/none."""

    type: str = field(validator=validators.in_(GROUP_TYPES))
    children: list = Factory(list)  # list[GroupNode | ComponentNode]

    def to_json(self):
        return {
            'type': self.type,
            'children': [child.to_json() for child in self.children],
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            type=data['type'],
            children=[node_from_json(c) for c in data.get('children', [])],
        )


def node_from_json(data):
    """Build a node tree from an already-validated raw spec."""
    node_type = data.get('type')
    if node_type in GROUP_TYPES:
        return GroupNode.from_json(data)
    if node_type == ComponentNode.type:
        return ComponentNode.from_json(data)
    raise ValueError(f'Unknown node type: {node_type!r}')


def parse_query_spec(query_spec, case_type_name, capability):
    """Validate a query spec against capability metadata and parse it.

    :returns: a ``(root, errors)`` tuple. ``root`` is the parsed node tree (an
        attrs ``GroupNode``/``ComponentNode``), or ``None`` when ``errors`` (a
        list of message strings) is non-empty.
    """
    errors = []
    fields_by_name = _fields_by_name(capability, case_type_name, errors)
    operator_input_schemas = capability.get('operator_input_schemas', {})

    _validate_node(query_spec, fields_by_name, operator_input_schemas, errors, depth=0, counter=[0])
    if errors:
        return None, errors
    return node_from_json(query_spec), errors


def _fields_by_name(capability, case_type_name, errors):
    case_types = capability.get('case_types', {})
    if case_type_name not in case_types:
        errors.append(f"Unknown case type: '{case_type_name}'")
        return {}
    return case_types[case_type_name]


def _validate_node(node, fields_by_name, operator_input_schemas, errors, depth, counter):
    counter[0] += 1
    if counter[0] > MAX_TOTAL_NODES:
        errors.append(f'Query has too many nodes (max {MAX_TOTAL_NODES})')
        return
    if not isinstance(node, dict):
        errors.append(
            f'Invalid node: expected object, got {type(node).__name__}'
        )
        return
    if depth > MAX_QUERY_DEPTH:
        errors.append(
            f'Query is nested too deeply (max {MAX_QUERY_DEPTH} levels)'
        )
        return

    node_type = node.get('type')
    if node_type in GROUP_TYPES:
        children = node.get('children', [])
        if len(children) > MAX_GROUP_WIDTH:
            errors.append(
                f'Group has too many conditions (max {MAX_GROUP_WIDTH})'
            )
            return
        for child in children:
            _validate_node(child, fields_by_name, operator_input_schemas, errors, depth + 1, counter)
    elif node_type == 'component':
        _validate_component(node, fields_by_name, operator_input_schemas, errors)
    else:
        errors.append(
            f"Invalid node type: '{node_type}'. Expected 'all', 'any', 'none', or 'component'."
        )


def _validate_component(node, fields_by_name, operator_input_schemas, errors):
    field_name = node.get('field', '')
    component_name = node.get('operator', '')
    inputs = node.get('inputs', {})

    field = fields_by_name.get(field_name)
    if not field:
        errors.append(f"Unknown field: '{field_name}'")
        return

    operation_names = [op['name'] for op in field.get('operations', [])]
    if component_name not in operation_names:
        errors.append(
            f"'{component_name}' is not a valid operation for field "
            f"'{field_name}' (type: {field['type']})"
        )
        return

    for slot in operator_input_schemas.get(component_name, []):
        slot_name = slot['name']
        if slot_name not in inputs:
            errors.append(
                f"Missing required input '{slot_name}' for component '{component_name}'"
            )
            continue
        _validate_input(inputs[slot_name], slot_name, errors)


def _validate_input(value, slot_name, errors):
    if not isinstance(value, dict):
        errors.append(
            f"Invalid input '{slot_name}': expected object, "
            f'got {type(value).__name__}'
        )
        return
    value_type = value.get('type')
    if value_type not in INPUT_TYPES:
        errors.append(f"Invalid input type '{value_type}' in '{slot_name}'")
