from unmagic import fixture, use

import pytest

from corehq.apps.case_search.endpoint_capability import (
    OPERATOR_INPUT_SCHEMAS,
    FIELD_TYPE_DATE,
    FIELD_TYPE_DATETIME,
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


def test_operator_input_schemas_shape():
    for op, schema in OPERATOR_INPUT_SCHEMAS.items():
        assert isinstance(schema, list), (
            f'{op}: expected list, got {type(schema)}'
        )
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
def test_capability_for_domain():
    cap = get_capability('test-domain')
    assert cap['case_types'].keys() == {'patient'}
    patient = cap['case_types']['patient']
    assert {'first_name', 'dob', 'status'} <= patient.keys()
    assert 'equals' in [op['name'] for op in patient['first_name']['operations']]
    assert set(patient['status']['options']) == {'active', 'closed'}
    assert cap['operator_input_schemas']


def test_operations_have_name_and_label():
    ops = get_operations_for_field_type(FIELD_TYPE_TEXT)
    assert ops
    for op in ops:
        assert isinstance(op['name'], str)
        # label is a lazy gettext proxy; force to str for the type check.
        assert isinstance(str(op['label']), str)


def test_date_operations_use_operator_names_not_before_after():
    labels = {op['name']: str(op['label']) for op in get_operations_for_field_type(FIELD_TYPE_DATE)}
    assert labels == {
        'equals': 'on',
        'lt': 'before',
        'gt': 'after',
        'lte': 'on or before',
        'gte': 'on or after',
        'fuzzy_date': 'is approximately',
    }


def test_fuzzy_date_is_not_offered_for_datetime():
    datetime_ops = {op['name'] for op in get_operations_for_field_type(FIELD_TYPE_DATETIME)}
    assert 'fuzzy_date' not in datetime_ops


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


@pytest.mark.parametrize("prop_name,prop_kwargs", [
    ('legacy_prop', {'data_type': CaseProperty.DataType.PLAIN, 'deprecated': True}),
    ('secret', {'data_type': CaseProperty.DataType.PASSWORD}),
])
@use(patient_case_type)
def test_excludes_property(prop_name, prop_kwargs):
    case_type = patient_case_type()
    prop = CaseProperty.objects.create(case_type=case_type, name=prop_name, **prop_kwargs)
    try:
        cap = get_capability('test-domain')
        assert prop_name not in cap['case_types']['patient'].keys()
    finally:
        prop.delete()


def test_get_field_type_raises_for_unmapped_data_type():
    with pytest.raises(ValueError, match="Unmapped"):
        get_field_type('totally_unknown_type')
