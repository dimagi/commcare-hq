"""Validation of case search endpoint query builder filter specs.

Validates a query builder filter spec against the capability metadata in
:mod:`.endpoint_capability`.
"""

from corehq.apps.case_search.endpoint_capability import COMPONENT_INPUT_SCHEMAS

# Maximum nesting depth of all/any/none groups.
MAX_QUERY_DEPTH = 5
# Maximum children per group.
MAX_GROUP_WIDTH = 50
# Maximum total nodes across the entire query tree.
MAX_TOTAL_NODES = 200


def validate_filter_spec(spec, case_type_name, capability):
    """Validate a query builder filter spec against capability metadata.

    Returns a list of error message strings (empty list = valid).
    """
    errors = []
    case_type = next(
        (
            case_type
            for case_type in capability.get('case_types', [])
            if case_type['name'] == case_type_name
        ),
        None,
    )
    fields_by_name = (
        {field['name']: field for field in case_type['fields']}
        if case_type
        else {}
    )

    _validate_node(spec, fields_by_name, errors, counter=[0])
    return errors


def _validate_node(node, fields_by_name, errors, depth=0, counter=None):
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

    if node_type in ('all', 'any', 'none'):
        children = node.get('children', [])
        if len(children) > MAX_GROUP_WIDTH:
            errors.append(
                f'Group has too many conditions (max {MAX_GROUP_WIDTH})'
            )
            return
        for child in children:
            _validate_node(
                child,
                fields_by_name,
                errors,
                depth + 1,
                counter,
            )
    elif node_type == 'component':
        _validate_component(node, fields_by_name, errors)
    else:
        errors.append(
            f"Invalid node type: '{node_type}'. Expected 'all', 'any', 'none', or 'component'."
        )


def _validate_component(node, fields_by_name, errors):
    field_name = node.get('field', '')
    component_name = node.get('component', '')
    inputs = node.get('inputs', {})

    field = fields_by_name.get(field_name)
    if not field:
        errors.append(f"Unknown field: '{field_name}'")
        return

    operation_names = [op['name'] for op in field.get('operations', [])]
    if component_name not in operation_names:
        errors.append(
            f"'{component_name}' is not a valid operation for field '{field_name}' "
            f'(type: {field["type"]})'
        )
        return

    schema = COMPONENT_INPUT_SCHEMAS.get(component_name, [])
    for slot in schema:
        slot_name = slot['name']
        if slot_name not in inputs:
            errors.append(
                f"Missing required input '{slot_name}' for component '{component_name}'"
            )
            continue
        _validate_input_value(inputs[slot_name], slot_name, errors)


def _validate_input_value(value, slot_name, errors):
    value_type = value.get('type')
    if value_type == 'constant':
        pass  # any value accepted
    else:
        errors.append(f"Invalid input type '{value_type}' in '{slot_name}'")
