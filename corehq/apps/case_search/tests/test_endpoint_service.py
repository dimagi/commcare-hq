import pytest
from unmagic import fixture, use

from django.http import Http404

from corehq.apps.case_search import endpoint_service
from corehq.apps.case_search.models import CaseSearchEndpoint
from corehq.apps.case_search.endpoint_capability import (
    _AUTO_VALUES,
    FIELD_TYPE_DATE,
    FIELD_TYPE_TEXT,
    get_operations_for_field_type,
)

DOMAIN = 'test-domain'
EMPTY_QUERY = {'type': 'and', 'children': []}
SAMPLE_QUERY = {
    'type': 'and',
    'children': [
        {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {
                'value': {'type': 'parameter', 'ref': 'search_province'},
            },
        },
    ],
}
SAMPLE_PARAMS = [{'name': 'search_province', 'type': 'text'}]


@use('db')
def test_creates_endpoint_and_first_version():
    endpoint = endpoint_service.create_endpoint(
        domain=DOMAIN, name='My Endpoint', target_type='project_db',
        target_name='patient',
        parameters=[{'name': 'q', 'type': 'text', 'required': True}],
        query=EMPTY_QUERY,
    )
    assert endpoint.current_version is not None
    assert endpoint.current_version.version_number == 1
    assert endpoint.current_version.parameters == [
        {'name': 'q', 'type': 'text', 'required': True}
    ]


@use('db')
def test_raises_on_duplicate_name():
    endpoint_service.create_endpoint(
        domain=DOMAIN, name='Dup', target_type='project_db',
        target_name='patient', parameters=[], query=EMPTY_QUERY,
    )
    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        endpoint_service.create_endpoint(
            domain=DOMAIN, name='Dup', target_type='project_db',
            target_name='patient', parameters=[], query=EMPTY_QUERY,
        )


@use('db')
@fixture
def versioned_endpoint():
    endpoint = endpoint_service.create_endpoint(
        domain=DOMAIN, name='Versioned', target_type='project_db',
        target_name='patient', parameters=[], query=EMPTY_QUERY,
    )
    try:
        yield endpoint
    finally:
        endpoint.delete()


@use(versioned_endpoint)
def test_increments_version_number():
    endpoint = versioned_endpoint()
    v2 = endpoint_service.save_new_version(
        endpoint,
        parameters=[{'name': 'p', 'type': 'text', 'required': False}],
        query={'type': 'or', 'children': []},
    )
    assert v2.version_number == 2
    endpoint.refresh_from_db()
    assert endpoint.current_version == v2


@use(versioned_endpoint)
def test_previous_version_unchanged():
    endpoint = versioned_endpoint()
    v1 = endpoint.current_version
    endpoint_service.save_new_version(
        endpoint, parameters=[], query={'type': 'or', 'children': []},
    )
    v1.refresh_from_db()
    assert v1.version_number == 1
    assert v1.query == EMPTY_QUERY


@use('db')
def test_returns_only_active_for_domain():
    endpoint_service.create_endpoint('d1', 'A', 'project_db', 'p', [], EMPTY_QUERY)
    endpoint_service.create_endpoint('d1', 'B', 'project_db', 'p', [], EMPTY_QUERY)
    endpoint_service.create_endpoint('d2', 'C', 'project_db', 'p', [], EMPTY_QUERY)
    ep_b = CaseSearchEndpoint.objects.get(domain='d1', name='B')
    endpoint_service.deactivate_endpoint(ep_b)
    result = endpoint_service.list_endpoints('d1')
    assert list(result.values_list('name', flat=True)) == ['A']


@use('db')
def test_get_endpoint_returns_for_domain():
    ep = endpoint_service.create_endpoint('d1', 'X', 'project_db', 'p', [], EMPTY_QUERY)
    fetched = endpoint_service.get_endpoint('d1', ep.id)
    assert fetched.pk == ep.pk


@use('db')
def test_get_endpoint_raises_404_wrong_domain():
    ep = endpoint_service.create_endpoint('d1', 'X', 'project_db', 'p', [], EMPTY_QUERY)
    with pytest.raises(Http404):
        endpoint_service.get_endpoint('d2', ep.id)


@use('db')
def test_deactivate_sets_is_active_false():
    ep = endpoint_service.create_endpoint('d1', 'Del', 'project_db', 'p', [], EMPTY_QUERY)
    endpoint_service.deactivate_endpoint(ep)
    ep.refresh_from_db()
    assert ep.is_active is False


@fixture
def sample_capability():
    yield {
        'case_types': [{
            'name': 'patient',
            'fields': [
                {
                    'name': 'province',
                    'type': FIELD_TYPE_TEXT,
                    'operations': get_operations_for_field_type(FIELD_TYPE_TEXT),
                },
                {
                    'name': 'dob',
                    'type': FIELD_TYPE_DATE,
                    'operations': get_operations_for_field_type(FIELD_TYPE_DATE),
                },
            ],
        }],
        'auto_values': _AUTO_VALUES,
    }


@use(sample_capability)
def test_valid_simple_spec():
    spec = {
        'type': 'and',
        'children': [{
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
        }],
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert errors == []


@use(sample_capability)
def test_valid_date_range_spec():
    spec = {
        'type': 'component',
        'component': 'date_range',
        'field': 'dob',
        'inputs': {
            'start': {'type': 'constant', 'value': '2000-01-01'},
            'end': {'type': 'auto_value', 'ref': 'today()'},
        },
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert errors == []


@use(sample_capability)
def test_invalid_root_type():
    spec = {'type': 'invalid'}
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('type' in e.lower() for e in errors)


@use(sample_capability)
def test_unknown_field():
    spec = {
        'type': 'component',
        'component': 'exact_match',
        'field': 'nonexistent',
        'inputs': {'value': {'type': 'constant', 'value': 'x'}},
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('nonexistent' in e for e in errors)


@use(sample_capability)
def test_incompatible_component_for_field():
    spec = {
        'type': 'component',
        'component': 'date_range',
        'field': 'province',
        'inputs': {
            'start': {'type': 'constant', 'value': '2000-01-01'},
            'end': {'type': 'constant', 'value': '2020-01-01'},
        },
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('date_range' in e for e in errors)


@use(sample_capability)
def test_missing_required_input_slot():
    spec = {
        'type': 'component',
        'component': 'date_range',
        'field': 'dob',
        'inputs': {'start': {'type': 'constant', 'value': '2000-01-01'}},
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('end' in e for e in errors)


@use(sample_capability)
def test_parameter_ref_must_exist():
    spec = {
        'type': 'component',
        'component': 'exact_match',
        'field': 'province',
        'inputs': {'value': {'type': 'parameter', 'ref': 'missing_param'}},
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('missing_param' in e for e in errors)


@use(sample_capability)
def test_parameter_ref_valid():
    spec = {
        'type': 'component',
        'component': 'exact_match',
        'field': 'province',
        'inputs': {'value': {'type': 'parameter', 'ref': 'search_province'}},
    }
    params = [{'name': 'search_province', 'type': 'text'}]
    errors = endpoint_service.validate_filter_spec(spec, params, 'patient', sample_capability())
    assert errors == []


@use(sample_capability)
def test_invalid_auto_value_ref():
    spec = {
        'type': 'component',
        'component': 'exact_match',
        'field': 'province',
        'inputs': {'value': {'type': 'auto_value', 'ref': 'nonexistent()'}},
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('nonexistent' in e for e in errors)


@use(sample_capability)
def test_not_node_with_valid_child():
    spec = {
        'type': 'not',
        'child': {
            'type': 'component',
            'component': 'exact_match',
            'field': 'province',
            'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
        },
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert errors == []


@use(sample_capability)
def test_not_node_missing_child():
    spec = {'type': 'not'}
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert any('child' in e for e in errors)


@use(sample_capability)
def test_nested_and_or():
    spec = {
        'type': 'and',
        'children': [{
            'type': 'or',
            'children': [{
                'type': 'component',
                'component': 'exact_match',
                'field': 'province',
                'inputs': {'value': {'type': 'constant', 'value': 'ON'}},
            }],
        }],
    }
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert errors == []


@use(sample_capability)
def test_empty_children_allowed():
    spec = {'type': 'and', 'children': []}
    errors = endpoint_service.validate_filter_spec(spec, [], 'patient', sample_capability())
    assert errors == []
