from unmagic import fixture, use

from corehq.apps.case_search.endpoint_capability import (
    FIELD_TYPE_DATE,
    FIELD_TYPE_GEOPOINT,
    FIELD_TYPE_TEXT,
    get_operations_for_field_type,
)
from corehq.apps.case_search.endpoint_query_spec import (
    MAX_GROUP_WIDTH,
    MAX_QUERY_DEPTH,
    ComponentNode,
    ConstantInput,
    GroupNode,
    parse_query_spec,
)


@fixture
def sample_capability():
    yield {
        'case_types': {
            'patient': {
                'province': {
                    'name': 'province',
                    'type': FIELD_TYPE_TEXT,
                    'operations': get_operations_for_field_type(
                        FIELD_TYPE_TEXT
                    ),
                },
                'dob': {
                    'name': 'dob',
                    'type': FIELD_TYPE_DATE,
                    'operations': get_operations_for_field_type(
                        FIELD_TYPE_DATE
                    ),
                },
                'location': {
                    'name': 'location',
                    'type': FIELD_TYPE_GEOPOINT,
                    'operations': get_operations_for_field_type(
                        FIELD_TYPE_GEOPOINT
                    ),
                },
            },
        },
    }


@use(sample_capability)
def test_valid_simple_spec():
    spec = {
        'type': 'all',
        'children': [
            {
                'type': 'component',
                'component': 'equals',
                'field': 'province',
                'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
            }
        ],
    }
    root, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert errors == []
    assert root == GroupNode(
        type='all',
        children=[
            ComponentNode(
                field='province',
                component='equals',
                inputs={'value': ConstantInput(value='ON')},
            )
        ],
    )


@use(sample_capability)
def test_valid_multi_input_spec():
    spec = {
        'type': 'component',
        'component': 'within_distance',
        'field': 'location',
        'inputs': {
            'point': {'type': 'constant', 'value': '0 0'},
            'distance': {'type': 'constant', 'value': '5'},
            'unit': {'type': 'constant', 'value': 'km'},
        },
    }
    root, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert errors == []
    assert isinstance(root, ComponentNode)
    assert set(root.inputs) == {'point', 'distance', 'unit'}
    assert root.inputs['distance'] == ConstantInput(value='5')


@use(sample_capability)
def test_ast_round_trips_through_json():
    spec = {
        'type': 'all',
        'children': [
            {
                'type': 'component',
                'field': 'province',
                'component': 'equals',
                'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
            }
        ],
    }
    root, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert errors == []
    assert root.to_json() == spec


@use(sample_capability)
def test_invalid_root_type():
    root, errors = parse_query_spec(
        {'type': 'invalid'}, 'patient', sample_capability()
    )
    assert root is None
    assert any('type' in e.lower() for e in errors)


@use(sample_capability)
def test_date_field_accepts_lt():
    spec = {
        'type': 'component',
        'component': 'lt',
        'field': 'dob',
        'inputs': {'value': {'type': 'constant', 'value': '2020-01-01'}},
    }
    root, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert errors == []
    assert isinstance(root, ComponentNode)
    assert root.component == 'lt'


@use(sample_capability)
def test_unknown_case_type():
    spec = {'type': 'all', 'children': []}
    root, errors = parse_query_spec(spec, 'nonexistent_type', sample_capability())
    assert root is None
    assert any('nonexistent_type' in e for e in errors)


@use(sample_capability)
def test_unknown_field():
    spec = {
        'type': 'component',
        'component': 'equals',
        'field': 'nonexistent',
        'inputs': {'value': {'type': 'constant', 'value': 'x'}},
    }
    root, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert root is None
    assert any('nonexistent' in e for e in errors)


@use(sample_capability)
def test_incompatible_component_for_field():
    spec = {
        'type': 'component',
        'component': 'within_distance',
        'field': 'province',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    _, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert any('within_distance' in e for e in errors)


@use(sample_capability)
def test_missing_required_input_slot():
    spec = {
        'type': 'component',
        'component': 'within_distance',
        'field': 'location',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    _, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert any('distance' in e for e in errors)


@use(sample_capability)
def test_non_constant_input_type_rejected():
    for input_type in ['parameter', 'auto_value']:
        spec = {
            'type': 'component',
            'component': 'equals',
            'field': 'province',
            'inputs': {'value': {'type': input_type, 'ref': 'some_ref'}},
        }
        _, errors = parse_query_spec(spec, 'patient', sample_capability())
        assert any('Invalid input type' in e for e in errors), input_type


@use(sample_capability)
def test_non_dict_input_rejected():
    spec = {
        'type': 'component',
        'component': 'equals',
        'field': 'province',
        'inputs': {'value': 'not_an_object'},
    }
    _, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert any('expected object' in e for e in errors)


@use(sample_capability)
def test_none_group_accepted():
    spec = {
        'type': 'none',
        'children': [
            {
                'type': 'component',
                'component': 'equals',
                'field': 'province',
                'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
            }
        ],
    }
    root, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert errors == []
    assert isinstance(root, GroupNode)
    assert root.type == 'none'


@use(sample_capability)
def test_nested_all_any():
    spec = {
        'type': 'all',
        'children': [
            {
                'type': 'any',
                'children': [
                    {
                        'type': 'component',
                        'component': 'equals',
                        'field': 'province',
                        'inputs': {
                            'value': {'type': 'constant', 'value': 'ON'}
                        },
                    }
                ],
            }
        ],
    }
    root, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert errors == []
    assert root.type == 'all'
    inner = root.children[0]
    assert isinstance(inner, GroupNode)
    assert inner.type == 'any'


@use(sample_capability)
def test_empty_children_allowed():
    root, errors = parse_query_spec(
        {'type': 'all', 'children': []}, 'patient', sample_capability()
    )
    assert errors == []
    assert root == GroupNode(type='all', children=[])


@use(sample_capability)
def test_non_dict_child_node_returns_error():
    spec = {'type': 'all', 'children': ['not_a_dict']}
    _, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert any('str' in e for e in errors)


@use(sample_capability)
def test_deeply_nested_query_returns_error():
    node = {'type': 'all', 'children': []}
    root = node
    for _ in range(MAX_QUERY_DEPTH + 2):
        child = {'type': 'all', 'children': []}
        node['children'] = [child]
        node = child
    _, errors = parse_query_spec(root, 'patient', sample_capability())
    assert any('nested too deeply' in e for e in errors)


@use(sample_capability)
def test_none_group_counts_toward_depth():
    # `none` is a regular group and counts toward the nesting limit like
    # `all`/`any` (the old `not` wrapper was exempt).
    node = {'type': 'none', 'children': []}
    root = node
    for _ in range(MAX_QUERY_DEPTH + 2):
        child = {'type': 'none', 'children': []}
        node['children'] = [child]
        node = child
    _, errors = parse_query_spec(root, 'patient', sample_capability())
    assert any('nested too deeply' in e for e in errors)


@use(sample_capability)
def test_group_exceeding_max_width_returns_error():
    spec = {
        'type': 'all',
        'children': [{'type': 'all', 'children': []}] * (MAX_GROUP_WIDTH + 1),
    }
    _, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert any('too many conditions' in e for e in errors)


@use(sample_capability)
def test_group_at_max_width_is_valid():
    spec = {
        'type': 'all',
        'children': [{'type': 'all', 'children': []}] * MAX_GROUP_WIDTH,
    }
    _, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert not any('too many conditions' in e for e in errors)


@use(sample_capability)
def test_total_node_limit_returns_error():
    # Wide-but-shallow: 1 + 50 + 50*4 = 251 > MAX_TOTAL_NODES (200). No group
    # exceeds the width limit, but the total node count does.
    spec = {
        'type': 'all',
        'children': [
            {
                'type': 'all',
                'children': [
                    {'type': 'all', 'children': []} for _ in range(4)
                ],
            }
            for _ in range(MAX_GROUP_WIDTH)
        ],
    }
    _, errors = parse_query_spec(spec, 'patient', sample_capability())
    assert any('too many nodes' in e for e in errors)
