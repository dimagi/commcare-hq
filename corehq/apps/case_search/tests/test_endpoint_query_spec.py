from unmagic import fixture, use

import pytest

from corehq.apps.case_search.endpoint_capability import (
    OPERATOR_INPUT_SCHEMAS,
    FIELD_TYPE_DATE,
    FIELD_TYPE_GEOPOINT,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_TEXT,
    get_operations_for_field_type,
)
from corehq.apps.case_search.endpoint_query_spec import (
    MAX_GROUP_WIDTH,
    MAX_QUERY_DEPTH,
    ComponentNode,
    ConstantInput,
    GroupNode,
    Parameter,
    parse_parameter_spec,
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
        'operator_input_schemas': OPERATOR_INPUT_SCHEMAS,
    }


@use(sample_capability)
def test_valid_simple_spec():
    spec = {
        'type': 'all',
        'children': [
            {
                'type': 'component',
                'operator': 'equals',
                'field': 'province',
                'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
            }
        ],
    }
    root, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert errors == []
    assert root == GroupNode(
        type='all',
        children=[
            ComponentNode(
                field='province',
                operator='equals',
                inputs={'value': ConstantInput(value='ON')},
                field_type='text',
            )
        ],
    )


@use(sample_capability)
def test_valid_multi_input_spec():
    spec = {
        'type': 'component',
        'operator': 'within_distance',
        'field': 'location',
        'inputs': {
            'point': {'type': 'constant', 'value': '0 0'},
            'distance': {'type': 'constant', 'value': '5'},
            'unit': {'type': 'constant', 'value': 'km'},
        },
    }
    root, errors = parse_query_spec(spec, [], 'patient', sample_capability())
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
                'operator': 'equals',
                'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
            }
        ],
    }
    root, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert errors == []
    assert root.to_json() == spec


@use(sample_capability)
def test_invalid_root_type():
    root, errors = parse_query_spec(
        {'type': 'invalid'}, [], 'patient', sample_capability()
    )
    assert root is None
    assert any('type' in e.lower() for e in errors)


@use(sample_capability)
def test_date_field_accepts_lt():
    spec = {
        'type': 'component',
        'operator': 'lt',
        'field': 'dob',
        'inputs': {'value': {'type': 'constant', 'value': '2020-01-01'}},
    }
    root, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert errors == []
    assert isinstance(root, ComponentNode)
    assert root.operator == 'lt'


@use(sample_capability)
def test_unknown_case_type():
    spec = {'type': 'all', 'children': []}
    root, errors = parse_query_spec(spec, [], 'nonexistent_type', sample_capability())
    assert root is None
    assert any('nonexistent_type' in e for e in errors)


@use(sample_capability)
def test_unknown_field():
    spec = {
        'type': 'component',
        'operator': 'equals',
        'field': 'nonexistent',
        'inputs': {'value': {'type': 'constant', 'value': 'x'}},
    }
    root, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert root is None
    assert any('nonexistent' in e for e in errors)


@use(sample_capability)
def test_incompatible_component_for_field():
    spec = {
        'type': 'component',
        'operator': 'within_distance',
        'field': 'province',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    _, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert any('within_distance' in e for e in errors)


@use(sample_capability)
def test_missing_required_input_slot():
    spec = {
        'type': 'component',
        'operator': 'within_distance',
        'field': 'location',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    _, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert any('distance' in e for e in errors)


@pytest.mark.parametrize("input_value,error_fragment", [
    ({'type': 'auto_value', 'ref': 'some_ref'}, 'Invalid input type'),
    ('not_an_object', 'expected object'),
])
@use(sample_capability)
def test_invalid_input_rejected(input_value, error_fragment):
    spec = {
        'type': 'component',
        'operator': 'equals',
        'field': 'province',
        'inputs': {'value': input_value},
    }
    _, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert any(error_fragment in e for e in errors)


@use(sample_capability)
def test_none_group_accepted():
    spec = {
        'type': 'none',
        'children': [
            {
                'type': 'component',
                'operator': 'equals',
                'field': 'province',
                'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
            }
        ],
    }
    root, errors = parse_query_spec(spec, [], 'patient', sample_capability())
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
                        'operator': 'equals',
                        'field': 'province',
                        'inputs': {
                            'value': {'type': 'constant', 'value': 'ON'}
                        },
                    }
                ],
            }
        ],
    }
    root, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert errors == []
    assert root.type == 'all'
    inner = root.children[0]
    assert isinstance(inner, GroupNode)
    assert inner.type == 'any'


@use(sample_capability)
def test_empty_children_allowed():
    root, errors = parse_query_spec(
        {'type': 'all', 'children': []}, [], 'patient', sample_capability()
    )
    assert errors == []
    assert root == GroupNode(type='all', children=[])


@use(sample_capability)
def test_non_dict_child_node_returns_error():
    spec = {'type': 'all', 'children': ['not_a_dict']}
    _, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert any('str' in e for e in errors)


@pytest.mark.parametrize("group_type", ["all", "none"])
@use(sample_capability)
def test_deeply_nested_group_returns_error(group_type):
    node = {'type': group_type, 'children': []}
    root = node
    for _ in range(MAX_QUERY_DEPTH + 2):
        child = {'type': group_type, 'children': []}
        node['children'] = [child]
        node = child
    _, errors = parse_query_spec(root, [], 'patient', sample_capability())
    assert any('nested too deeply' in e for e in errors)


@use(sample_capability)
def test_group_exceeding_max_width_returns_error():
    spec = {
        'type': 'all',
        'children': [{'type': 'all', 'children': []}] * (MAX_GROUP_WIDTH + 1),
    }
    _, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert any('too many conditions' in e for e in errors)


@use(sample_capability)
def test_group_at_max_width_is_valid():
    spec = {
        'type': 'all',
        'children': [{'type': 'all', 'children': []}] * MAX_GROUP_WIDTH,
    }
    _, errors = parse_query_spec(spec, [], 'patient', sample_capability())
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
    _, errors = parse_query_spec(spec, [], 'patient', sample_capability())
    assert any('too many nodes' in e for e in errors)


# ── parse_parameter_spec ──────────────────────────────────────────────────────

def test_parse_parameter_spec_empty_list():
    params, errors = parse_parameter_spec([])
    assert errors == []
    assert params == []


def test_parse_parameter_spec_valid_single():
    params, errors = parse_parameter_spec([{'name': 'region', 'type': FIELD_TYPE_TEXT}])
    assert errors == []
    assert params == [Parameter(name='region', type=FIELD_TYPE_TEXT)]


def test_parse_parameter_spec_multiple():
    spec = [
        {'name': 'region', 'type': FIELD_TYPE_TEXT},
        {'name': 'age', 'type': FIELD_TYPE_NUMBER},
    ]
    params, errors = parse_parameter_spec(spec)
    assert errors == []
    assert len(params) == 2


def test_parse_parameter_spec_strips_name_whitespace():
    params, errors = parse_parameter_spec([{'name': '  region  ', 'type': FIELD_TYPE_TEXT}])
    assert errors == []
    assert params[0].name == 'region'


def test_parse_parameter_spec_not_a_list():
    params, errors = parse_parameter_spec({'name': 'region'})
    assert params is None
    assert errors == ['Parameters must be a JSON array.']


@pytest.mark.parametrize("spec_input,error_fragment", [
    (['not_a_dict'], 'expected object'),
    ([{'type': FIELD_TYPE_TEXT}], 'name is required'),
    ([{'name': '   ', 'type': FIELD_TYPE_TEXT}], 'name is required'),
    ([{'name': 'region', 'type': FIELD_TYPE_TEXT}, {'name': 'region', 'type': FIELD_TYPE_NUMBER}], 'Duplicate'),
    ([{'name': 'region', 'type': 'bogus'}], "invalid type 'bogus'"),
])
def test_parse_parameter_spec_invalid(spec_input, error_fragment):
    _, errors = parse_parameter_spec(spec_input)
    assert any(error_fragment in e for e in errors)


@pytest.mark.parametrize("type_val", [FIELD_TYPE_TEXT, FIELD_TYPE_NUMBER, FIELD_TYPE_DATE])
def test_parse_parameter_spec_all_valid_types(type_val):
    params, errors = parse_parameter_spec([{'name': 'p', 'type': type_val}])
    assert errors == []
    assert params[0].type == type_val


# ── parameter input validation in parse_query_spec ───────────────────────────

def _component_spec(field, operator, input_value):
    return {
        'type': 'all',
        'children': [
            {
                'type': 'component',
                'field': field,
                'operator': operator,
                'inputs': {'value': input_value},
            }
        ],
    }


@pytest.mark.parametrize("field,param_name,param_type", [
    ('province', 'region', FIELD_TYPE_TEXT),
    ('dob', 'cutoff', FIELD_TYPE_DATE),
])
@use(sample_capability)
def test_parameter_input_valid(field, param_name, param_type):
    params = [Parameter(name=param_name, type=param_type)]
    _, errors = parse_query_spec(
        _component_spec(field, 'equals', {'type': 'parameter', 'value': param_name}),
        params, 'patient', sample_capability(),
    )
    assert errors == []


@pytest.mark.parametrize("params,input_value,error_fragment", [
    ([], {'type': 'parameter', 'value': 'nonexistent'}, 'not configured'),
    (
        [Parameter(name='region', type=FIELD_TYPE_TEXT)],
        {'type': 'parameter', 'value': ''},
        'parameter name is required',
    ),
    (
        [Parameter(name='my_date', type=FIELD_TYPE_DATE)],
        {'type': 'parameter', 'value': 'my_date'},
        "has type 'date', expected 'text'",
    ),
])
@use(sample_capability)
def test_parameter_input_error(params, input_value, error_fragment):
    _, errors = parse_query_spec(
        _component_spec('province', 'equals', input_value),
        params, 'patient', sample_capability(),
    )
    assert any(error_fragment in e for e in errors)
