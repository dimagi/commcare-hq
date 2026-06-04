from unmagic import fixture, use

from corehq.apps.case_search.endpoint_capability import (
    MAX_GROUP_WIDTH,
    MAX_QUERY_DEPTH,
    COMPONENT_INPUT_SCHEMAS,
    FIELD_TYPE_DATE,
    FIELD_TYPE_GEOPOINT,
    FIELD_TYPE_TEXT,
    get_capability,
    get_operations_for_field_type,
    validate_filter_spec,
)
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CaseType,
)


def test_component_input_schemas_all_values_are_lists():
    for op, schema in COMPONENT_INPUT_SCHEMAS.items():
        assert isinstance(schema, list), (
            f'{op}: expected list, got {type(schema)}'
        )


def test_component_input_schemas_all_items_have_name_and_type_strings():
    for op, schema in COMPONENT_INPUT_SCHEMAS.items():
        for item in schema:
            assert isinstance(item.get('name'), str), (
                f"{op}: item 'name' must be str"
            )
            assert isinstance(item.get('type'), str), (
                f"{op}: item 'type' must be str"
            )


@use('db')
@fixture
def patient_case_type():
    case_type = CaseType.objects.create(domain='test-domain', name='patient')
    CaseProperty.objects.create(
        case_type=case_type,
        name='first_name',
        data_type=CaseProperty.DataType.PLAIN,
    )
    CaseProperty.objects.create(
        case_type=case_type,
        name='dob',
        data_type=CaseProperty.DataType.DATE,
    )
    prop_status = CaseProperty.objects.create(
        case_type=case_type,
        name='status',
        data_type=CaseProperty.DataType.SELECT,
    )
    CasePropertyAllowedValue.objects.create(
        case_property=prop_status, allowed_value='active'
    )
    CasePropertyAllowedValue.objects.create(
        case_property=prop_status, allowed_value='closed'
    )
    try:
        yield case_type
    finally:
        case_type.delete()


@use(patient_case_type)
def test_returns_case_types_with_fields():
    cap = get_capability('test-domain')
    assert len(cap['case_types']) == 1
    ct = cap['case_types'][0]
    assert ct['name'] == 'patient'
    field_names = [f['name'] for f in ct['fields']]
    assert 'first_name' in field_names
    assert 'dob' in field_names


@use(patient_case_type)
def test_field_has_operations():
    cap = get_capability('test-domain')
    ct = cap['case_types'][0]
    name_field = next(f for f in ct['fields'] if f['name'] == 'first_name')
    assert 'equals' in name_field['operations']


@use(patient_case_type)
def test_select_field_has_options():
    cap = get_capability('test-domain')
    ct = cap['case_types'][0]
    status_field = next(f for f in ct['fields'] if f['name'] == 'status')
    assert set(status_field['options']) == {'active', 'closed'}


@use(patient_case_type)
def test_excludes_deprecated_case_types():
    deprecated = CaseType.objects.create(
        domain='test-domain', name='old_type', is_deprecated=True
    )
    try:
        cap = get_capability('test-domain')
        names = [ct['name'] for ct in cap['case_types']]
        assert 'old_type' not in names
    finally:
        deprecated.delete()


@use(patient_case_type)
def test_excludes_deprecated_properties():
    case_type = patient_case_type()
    legacy = CaseProperty.objects.create(
        case_type=case_type,
        name='legacy_prop',
        data_type=CaseProperty.DataType.PLAIN,
        deprecated=True,
    )
    try:
        cap = get_capability('test-domain')
        ct = cap['case_types'][0]
        field_names = [f['name'] for f in ct['fields']]
        assert 'legacy_prop' not in field_names
    finally:
        legacy.delete()


@use(patient_case_type)
def test_excludes_password_fields():
    case_type = patient_case_type()
    secret = CaseProperty.objects.create(
        case_type=case_type,
        name='secret',
        data_type=CaseProperty.DataType.PASSWORD,
    )
    try:
        cap = get_capability('test-domain')
        ct = cap['case_types'][0]
        field_names = [f['name'] for f in ct['fields']]
        assert 'secret' not in field_names
    finally:
        secret.delete()


@use(patient_case_type)
def test_component_input_schemas_present():
    cap = get_capability('test-domain')
    assert 'component_input_schemas' in cap
    assert 'exact_match' in cap['component_input_schemas']


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
        'type': 'and',
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
def test_not_node_with_valid_child():
    spec = {
        'type': 'not',
        'child': {
            'type': 'component',
            'component': 'equals',
            'field': 'province',
            'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
        },
    }
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


@use(sample_capability)
def test_not_node_missing_child():
    errors = validate_filter_spec(
        {'type': 'not'}, 'patient', sample_capability()
    )
    assert any('child' in e for e in errors)


@use(sample_capability)
def test_directly_nested_not_rejected():
    spec = {
        'type': 'not',
        'child': {'type': 'not', 'child': {'type': 'and', 'children': []}},
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any("another 'not'" in e for e in errors)


@use(sample_capability)
def test_nested_and_or():
    spec = {
        'type': 'and',
        'children': [
            {
                'type': 'or',
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
    spec = {'type': 'and', 'children': []}
    assert validate_filter_spec(spec, 'patient', sample_capability()) == []


@use(sample_capability)
def test_non_dict_child_node_returns_error():
    spec = {'type': 'and', 'children': ['not_a_dict']}
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('str' in e for e in errors)


@use(sample_capability)
def test_deeply_nested_query_returns_error():
    node = {'type': 'and', 'children': []}
    root = node
    for _ in range(MAX_QUERY_DEPTH + 2):
        child = {'type': 'and', 'children': []}
        node['children'] = [child]
        node = child
    errors = validate_filter_spec(root, 'patient', sample_capability())
    assert any('nested too deeply' in e for e in errors)


@use(sample_capability)
def test_not_nodes_do_not_count_towards_depth():
    # Max-depth and/or nesting stays valid even when every group is negated.
    node = {'type': 'and', 'children': []}
    root = {'type': 'not', 'child': node}
    for _ in range(MAX_QUERY_DEPTH):
        child = {'type': 'and', 'children': []}
        node['children'] = [{'type': 'not', 'child': child}]
        node = child
    assert validate_filter_spec(root, 'patient', sample_capability()) == []


@use(sample_capability)
def test_group_exceeding_max_width_returns_error():
    spec = {
        'type': 'and',
        'children': [{'type': 'and', 'children': []}] * (MAX_GROUP_WIDTH + 1),
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('too many conditions' in e for e in errors)


@use(sample_capability)
def test_group_at_max_width_is_valid():
    spec = {
        'type': 'and',
        'children': [{'type': 'and', 'children': []}] * MAX_GROUP_WIDTH,
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert not any('too many conditions' in e for e in errors)


@use(sample_capability)
def test_total_node_limit_returns_error():
    # Build a wide-but-shallow tree: root has MAX_GROUP_WIDTH children,
    # each with 4 children.  No group exceeds the width limit, but total
    # nodes = 1 + 50 + 50*4 = 251 > MAX_TOTAL_NODES (200).
    spec = {
        'type': 'and',
        'children': [
            {
                'type': 'and',
                'children': [
                    {'type': 'and', 'children': []} for _ in range(4)
                ],
            }
            for _ in range(MAX_GROUP_WIDTH)
        ],
    }
    errors = validate_filter_spec(spec, 'patient', sample_capability())
    assert any('too many nodes' in e for e in errors)
