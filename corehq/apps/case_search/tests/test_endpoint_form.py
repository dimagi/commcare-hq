"""Tests for the cleaning done by ``CaseSearchEndpointForm``.

The endpoint view tests cover what a view does with a valid or an invalid
form. These cover the form's own validation, which needs no logged-in user,
request or rendered template.
"""
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

import pytest
from sqlalchemy.exc import OperationalError
from unmagic import use

from corehq.apps.case_search.endpoint_capability import (
    OPERATOR_INPUT_SCHEMAS,
    FIELD_TYPE_TEXT,
    get_operations_for_field_type,
)
from corehq.apps.project_db.tests.util import project_db_table

from ..endpoint_views import CaseSearchEndpointForm, empty_query
from ..models import CaseSearchEndpoint

DOMAIN = 'endpoint-form-test'
CASE_TYPE = 'my_case_type'
CAPABILITY = {
    'case_types': {
        CASE_TYPE: {
            'nickname': {
                'name': 'nickname',
                'type': FIELD_TYPE_TEXT,
                'operations': get_operations_for_field_type(FIELD_TYPE_TEXT),
            },
        },
    },
    'operator_input_schemas': OPERATOR_INPUT_SCHEMAS,
}
ES = CaseSearchEndpoint.TargetType.ELASTICSEARCH
PROJECT_DB = CaseSearchEndpoint.TargetType.PROJECT_DB


def bound_form(target_type=ES, exclude_pk=None, **data):
    data.setdefault('name', 'an-endpoint')
    data.setdefault('case_type', CASE_TYPE)
    form = CaseSearchEndpointForm(
        data,
        domain=DOMAIN,
        target_type=target_type,
        exclude_pk=exclude_pk,
        capability=CAPABILITY,
    )
    form.is_valid()
    return form


@use('db')
def test_omitted_query_and_parameters_get_defaults():
    form = bound_form()
    assert form.errors == {}
    assert form.cleaned_data['query'] == empty_query()
    assert form.cleaned_data['parameters'] == []


@pytest.mark.parametrize('data,field,error_fragment', [
    ({'query': 'not json'}, 'query', 'valid JSON'),
    ({'query': '[1, 2]'}, 'query', 'JSON object'),
    ({'parameters': '{"not": "array"}'}, 'parameters', 'JSON array'),
])
@use('db')
def test_field_validation_error(data, field, error_fragment):
    form = bound_form(**data)
    assert error_fragment in form.errors[field][0]


@use('db')
def test_invalid_query_spec_is_a_non_field_error():
    # A spec that parses as JSON but is not a query the builder understands
    # is a semantic error, so it belongs to the form rather than a field.
    form = bound_form(query='{"type": "bogus"}')
    assert form.errors == {'__all__': ['Invalid query']}


@use('db')
def test_duplicate_name_rejected():
    endpoint = CaseSearchEndpoint.objects.create(
        domain=DOMAIN, name='existing', target_type=ES
    )
    assert 'already exists' in bound_form(name='existing').errors['name'][0]
    # ...but an endpoint may keep its own name when it is edited
    assert 'name' not in bound_form(name='existing', exclude_pk=endpoint.pk).errors


@use('db')
def test_elasticsearch_target_drops_sql():
    form = bound_form(sql='DROP TABLE my_case_type')
    assert form.errors == {}
    assert form.cleaned_data['sql'] == ''


@use('db')
def test_project_db_target_drops_elasticsearch_fields():
    # Elasticsearch fields are dropped rather than validated, so a spec
    # Elasticsearch would reject does not make a project_db endpoint invalid.
    with project_db_table(DOMAIN, CASE_TYPE, {'nickname': 'plain'}):
        form = bound_form(
            target_type=PROJECT_DB,
            sql=f'SELECT case_id FROM {CASE_TYPE}',
            query='{"type": "bogus"}',
        )
    assert form.errors == {}
    assert form.cleaned_data['case_type'] is None
    assert form.cleaned_data['query'] is None


@pytest.mark.parametrize('sql,expected', [
    ('', 'SQL is required.'),
    # translate() rejects plenty more; see project_db's own tests
    (f'SELECT nope FROM {CASE_TYPE}', 'unknown column'),
])
@use('db')
def test_project_db_sql_error(sql, expected):
    with project_db_table(DOMAIN, CASE_TYPE, {'nickname': 'plain'}):
        form = bound_form(target_type=PROJECT_DB, sql=sql)
    assert expected in form.errors['sql'][0]


@pytest.mark.parametrize('error', [
    ImproperlyConfigured("'project_db' database not defined"),
    OperationalError('connection refused', None, None),
])
@use('db')
def test_project_db_unavailable_is_not_the_authors_fault(error):
    # The engine falls back to the default database under DEBUG or
    # UNIT_TESTING, so the failure has to be injected to be reachable.
    with patch(
        'corehq.apps.case_search.endpoint_views.get_domain_tables',
        side_effect=error,
    ):
        form = bound_form(target_type=PROJECT_DB, sql='SELECT case_id FROM x')
    assert 'unavailable' in form.non_field_errors()[0]
    assert 'sql' not in form.errors
