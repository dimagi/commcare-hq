from unmagic import fixture, use

from corehq.apps.case_search.endpoint_capability import (
    FIELD_TYPE_DATE,
    FIELD_TYPE_GEOPOINT,
    FIELD_TYPE_TEXT,
    get_operations_for_field_type,
)
from corehq.apps.case_search.filter_spec import (
    MAX_GROUP_WIDTH,
    MAX_QUERY_DEPTH,
    validate_filter_spec,
)


@fixture
def sample_capability():
    yield {
        'case_types': [
            {
                'name': 'patient',
                'fields': [
                    {
                        'name': 'province',
                        'type': FIELD_TYPE_TEXT,
                        'operations': get_operations_for_field_type(
                            FIELD_TYPE_TEXT
                        ),
                    },
                    {
                        'name': 'dob',
                        'type': FIELD_TYPE_DATE,
                        'operations': get_operations_for_field_type(
                            FIELD_TYPE_DATE
                        ),
                    },
                    {
                        'name': 'location',
                        'type': FIELD_TYPE_GEOPOINT,
                        'operations': get_operations_for_field_type(
                            FIELD_TYPE_GEOPOINT
                        ),
                    },
                ],
            }
        ],
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
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


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
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


@use(sample_capability)
def test_invalid_root_type():
    errors = validate_filter_spec(
        {'type': 'invalid'}, 'patient', sample_capability()
    )
    assert any('type' in e.lower() for e in errors)


@use(sample_capability)
def test_date_field_accepts_lt():
    spec = {
        'type': 'component',
        'component': 'lt',
        'field': 'dob',
        'inputs': {'value': {'type': 'constant', 'value': '2020-01-01'}},
    }
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


@use(sample_capability)
def test_unknown_field():
    spec = {
        'type': 'component',
        'component': 'equals',
        'field': 'nonexistent',
        'inputs': {'value': {'type': 'constant', 'value': 'x'}},
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('nonexistent' in e for e in errors)


@use(sample_capability)
def test_incompatible_component_for_field():
    spec = {
        'type': 'component',
        'component': 'within_distance',
        'field': 'province',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('within_distance' in e for e in errors)


@use(sample_capability)
def test_missing_required_input_slot():
    spec = {
        'type': 'component',
        'component': 'within_distance',
        'field': 'location',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
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
        errors = validate_filter_spec(spec, 'patient', sample_capability())
        assert any('Invalid input type' in e for e in errors), input_type


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
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


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
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


@use(sample_capability)
def test_empty_children_allowed():
    spec = {'type': 'all', 'children': []}
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


@use(sample_capability)
def test_non_dict_child_node_returns_error():
    spec = {'type': 'all', 'children': ['not_a_dict']}
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('str' in e for e in errors)


@use(sample_capability)
def test_deeply_nested_query_returns_error():
    node = {'type': 'all', 'children': []}
    root = node
    for _ in range(MAX_QUERY_DEPTH + 2):
        child = {'type': 'all', 'children': []}
        node['children'] = [child]
        node = child
    errors = validate_filter_spec(root, 'patient', sample_capability())
    assert any('nested too deeply' in e for e in errors)


@use(sample_capability)
def test_none_group_counts_toward_depth():
    # Unlike the old `not` wrapper, `none` is a regular group and counts
    # toward the nesting limit like `all`/`any`.
    node = {'type': 'none', 'children': []}
    root = node
    for _ in range(MAX_QUERY_DEPTH + 2):
        child = {'type': 'none', 'children': []}
        node['children'] = [child]
        node = child
    errors = validate_filter_spec(root, 'patient', sample_capability())
    assert any('nested too deeply' in e for e in errors)


@use(sample_capability)
def test_group_exceeding_max_width_returns_error():
    spec = {
        'type': 'all',
        'children': [{'type': 'all', 'children': []}] * (MAX_GROUP_WIDTH + 1),
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('too many conditions' in e for e in errors)


@use(sample_capability)
def test_group_at_max_width_is_valid():
    spec = {
        'type': 'all',
        'children': [{'type': 'all', 'children': []}] * MAX_GROUP_WIDTH,
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert not any('too many conditions' in e for e in errors)


@use(sample_capability)
def test_total_node_limit_returns_error():
    # Build a wide-but-shallow tree: root has MAX_GROUP_WIDTH children,
    # each with 4 children.  No group exceeds the width limit, but total
    # nodes = 1 + 50 + 50*4 = 251 > MAX_TOTAL_NODES (200).
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
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('too many nodes' in e for e in errors)
