from unmagic import fixture, use

from corehq.apps.case_search.endpoint_capability import (
    COMPONENT_INPUT_SCHEMAS,
    _AUTO_VALUES,
    _MAX_QUERY_DEPTH,
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


def test_auto_values_all_values_are_lists():
    for field_type, values in _AUTO_VALUES.items():
        assert isinstance(values, list), (
            f'{field_type}: expected list, got {type(values)}'
        )


def test_auto_values_all_items_have_ref_and_label_strings():
    for field_type, values in _AUTO_VALUES.items():
        for item in values:
            assert isinstance(item.get('ref'), str), (
                f"{field_type}: item 'ref' must be str"
            )
            assert isinstance(item.get('label'), str), (
                f"{field_type}: item 'label' must be str"
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
def test_auto_values_present():
    cap = get_capability('test-domain')
    assert FIELD_TYPE_DATE in cap['auto_values']
    assert FIELD_TYPE_TEXT in cap['auto_values']


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
        'auto_values': _AUTO_VALUES,
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
    assert validate_filter_spec(spec, [], 'patient', sample_capability()) == []


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
    assert validate_filter_spec(spec, [], 'patient', sample_capability()) == []


@use(sample_capability)
def test_invalid_root_type():
    errors = validate_filter_spec(
        {'type': 'invalid'}, [], 'patient', sample_capability()
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
    errors = validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('nonexistent' in e for e in errors)


@use(sample_capability)
def test_incompatible_component_for_field():
    spec = {
        'type': 'component',
        'component': 'within_distance',
        'field': 'province',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    errors = validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('within_distance' in e for e in errors)


@use(sample_capability)
def test_missing_required_input_slot():
    spec = {
        'type': 'component',
        'component': 'within_distance',
        'field': 'location',
        'inputs': {'point': {'type': 'constant', 'value': '0 0'}},
    }
    errors = validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('distance' in e for e in errors)


@use(sample_capability)
def test_malformed_parameter_returns_error():
    errors = validate_filter_spec(
        {'type': 'and', 'children': []}, [{}], 'patient', sample_capability()
    )
    assert any('name' in e for e in errors)


@use(sample_capability)
def test_parameter_ref_must_exist():
    spec = {
        'type': 'component',
        'component': 'equals',
        'field': 'province',
        'inputs': {'value': {'type': 'parameter', 'ref': 'missing_param'}},
    }
    errors = validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('missing_param' in e for e in errors)


@use(sample_capability)
def test_parameter_ref_valid():
    spec = {
        'type': 'component',
        'component': 'equals',
        'field': 'province',
        'inputs': {'value': {'type': 'parameter', 'ref': 'search_province'}},
    }
    params = [{'name': 'search_province', 'type': 'text'}]
    assert (
        validate_filter_spec(spec, params, 'patient', sample_capability())
        == []
    )


@use(sample_capability)
def test_invalid_auto_value_ref():
    spec = {
        'type': 'component',
        'component': 'equals',
        'field': 'province',
        'inputs': {'value': {'type': 'auto_value', 'ref': 'nonexistent()'}},
    }
    errors = validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('nonexistent' in e for e in errors)


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
    assert validate_filter_spec(spec, [], 'patient', sample_capability()) == []


@use(sample_capability)
def test_not_node_missing_child():
    errors = validate_filter_spec(
        {'type': 'not'}, [], 'patient', sample_capability()
    )
    assert any('child' in e for e in errors)


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
    assert validate_filter_spec(spec, [], 'patient', sample_capability()) == []


@use(sample_capability)
def test_empty_children_allowed():
    spec = {'type': 'and', 'children': []}
    assert validate_filter_spec(spec, [], 'patient', sample_capability()) == []


@use(sample_capability)
def test_non_dict_child_node_returns_error():
    spec = {'type': 'and', 'children': ['not_a_dict']}
    errors = validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('str' in e for e in errors)


@use(sample_capability)
def test_deeply_nested_query_returns_error():
    node = {'type': 'and', 'children': []}
    root = node
    for _ in range(_MAX_QUERY_DEPTH + 2):
        child = {'type': 'and', 'children': []}
        node['children'] = [child]
        node = child
    errors = validate_filter_spec(root, [], 'patient', sample_capability())
    assert any('nested too deeply' in e for e in errors)
