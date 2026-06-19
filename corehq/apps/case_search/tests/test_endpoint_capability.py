from unmagic import fixture, use

import pytest

from corehq.apps.case_search.endpoint_capability import (
    OPERATOR_INPUT_SCHEMAS,
    FIELD_TYPE_DATE,
    FIELD_TYPE_TEXT,
    get_capability,
    get_field_type,
    get_operations_for_field_type,
)
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CaseType,
)


def test_operator_input_schemas_all_values_are_lists():
    for op, schema in OPERATOR_INPUT_SCHEMAS.items():
        assert isinstance(schema, list), (
            f'{op}: expected list, got {type(schema)}'
        )


def test_operator_input_schemas_all_items_have_name_and_type_strings():
    for op, schema in OPERATOR_INPUT_SCHEMAS.items():
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
    assert cap['case_types'].keys() == {'patient'}
    field_names = cap['case_types']['patient'].keys()
    assert 'first_name' in field_names
    assert 'dob' in field_names


@use(patient_case_type)
def test_field_has_operations():
    cap = get_capability('test-domain')
    name_field = cap['case_types']['patient']['first_name']
    op_names = [op['name'] for op in name_field['operations']]
    assert 'equals' in op_names


def test_operations_have_name_and_label():
    ops = get_operations_for_field_type(FIELD_TYPE_TEXT)
    assert ops
    for op in ops:
        assert isinstance(op['name'], str)
        # label is a lazy gettext proxy; force to str for the type check.
        assert isinstance(str(op['label']), str)


def test_date_operations_use_lt_gt_not_before_after():
    op_names = {op['name'] for op in get_operations_for_field_type(FIELD_TYPE_DATE)}
    assert op_names == {'equals', 'lt', 'gt'}
    assert 'before' not in op_names
    assert 'after' not in op_names


def test_date_lt_gt_labels_match_data_cleaning_phrasing():
    labels = {
        op['name']: str(op['label'])
        for op in get_operations_for_field_type(FIELD_TYPE_DATE)
    }
    assert labels['lt'] == 'before'
    assert labels['gt'] == 'after'
    assert labels['equals'] == 'on'


@use(patient_case_type)
def test_select_field_has_options():
    cap = get_capability('test-domain')
    status_field = cap['case_types']['patient']['status']
    assert set(status_field['options']) == {'active', 'closed'}


@use(patient_case_type)
def test_excludes_deprecated_case_types():
    deprecated = CaseType.objects.create(
        domain='test-domain', name='old_type', is_deprecated=True
    )
    try:
        cap = get_capability('test-domain')
        names = cap['case_types'].keys()
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
        field_names = cap['case_types']['patient'].keys()
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
        field_names = cap['case_types']['patient'].keys()
        assert 'secret' not in field_names
    finally:
        secret.delete()


def test_get_field_type_raises_for_unmapped_data_type():
    with pytest.raises(ValueError, match="Unmapped"):
        get_field_type('totally_unknown_type')


@use(patient_case_type)
def test_operator_input_schemas_present():
    cap = get_capability('test-domain')
    assert 'operator_input_schemas' in cap
    assert cap['operator_input_schemas']
