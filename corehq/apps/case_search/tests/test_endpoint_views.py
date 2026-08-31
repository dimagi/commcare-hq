import json
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

import pytest
from sqlalchemy import ARRAY, Text, bindparam
from sqlalchemy.exc import OperationalError

from corehq.apps.case_search.endpoint_capability import (
    FIELD_TYPE_DATERANGE,
    FIELD_TYPE_SELECT,
    FIELD_TYPE_TEXT,
)
from corehq.apps.case_search.endpoint_query_spec import Parameter
from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.project_db.tests.util import project_db_table
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled

from ..endpoint_views import (
    CaseSearchEndpointDeactivateView,
    CaseSearchEndpointEditView,
    CaseSearchEndpointNewView,
    CaseSearchEndpointsView,
    CaseSearchEndpointTestView,
    sql_parameter_errors,
)
from ..models import CaseSearchEndpoint, CaseSearchEndpointVersion

EMPTY_QUERY = {'type': 'all', 'children': []}


class EndpointViewTestCase(TestCase):
    domain = 'endpoint-view-test'
    username = 'testuser@example.com'

    @classmethod
    def setUpTestData(cls):
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(
            cls.domain, cls.username, 'password', None, None, is_admin=True
        )
        cls.addClassCleanup(cls.user.delete, cls.domain, None)
        for name in ('my_case_type', 'case_type_a', 'new_target'):
            ct = CaseType.objects.create(domain=cls.domain, name=name)
            cls.addClassCleanup(ct.delete)

    def setUp(self):
        self.client.login(username=self.username, password='password')
        flag = flag_enabled('CASE_SEARCH_ENDPOINTS')
        flag.__enter__()
        self.addCleanup(flag.__exit__, None, None, None)

    def _make_endpoint(self, name='my-endpoint', case_type='case_type_a',
                       target_type=CaseSearchEndpoint.TargetType.ELASTICSEARCH):
        endpoint = CaseSearchEndpoint.objects.create(
            domain=self.domain,
            name=name,
            target_type=target_type,
        )
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=endpoint,
            version_number=1,
            case_type=case_type,
            query=dict(EMPTY_QUERY),
            parameters=[],
            action=CaseSearchEndpointVersion.Action.CREATE,
        )
        endpoint.current_version = version
        endpoint.save(update_fields=['current_version'])
        return endpoint

    def _project_db_table(self, case_type='my_case_type'):
        return project_db_table(
            self.domain, case_type, {'nickname': 'plain', 'tags': 'select'}
        )

    def _list_url(self):
        return reverse(CaseSearchEndpointsView.urlname, args=[self.domain])

    def _new_url(self, target_type=CaseSearchEndpoint.TargetType.ELASTICSEARCH):
        url = reverse(CaseSearchEndpointNewView.urlname, args=[self.domain])
        return f'{url}?target_type={target_type}' if target_type else url

    def _edit_url(self, endpoint_id):
        return reverse(
            CaseSearchEndpointEditView.urlname, args=[self.domain, endpoint_id]
        )

    def _deactivate_url(self, endpoint_id):
        return reverse(
            CaseSearchEndpointDeactivateView.urlname,
            args=[self.domain, endpoint_id],
        )

    def _test_url(self):
        return reverse(CaseSearchEndpointTestView.urlname, args=[self.domain])

    def _post_data(self, **overrides):
        data = {
            'name': 'an-endpoint',
            'case_type': 'my_case_type',
            'query': json.dumps(EMPTY_QUERY),
            'parameters': '[]',
        }
        data.update(overrides)
        return data


class TestEndpointViewAccess(EndpointViewTestCase):
    nonadmin_username = 'nonadmin@example.com'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.nonadmin = WebUser.create(
            cls.domain, cls.nonadmin_username, 'password', None, None
        )
        cls.addClassCleanup(cls.nonadmin.delete, cls.domain, None)

    def setUp(self):
        super().setUp()
        self.client.login(username=self.nonadmin_username, password='password')

    def test_nonadmin_member_is_denied(self):
        ep = self._make_endpoint()
        cases = [
            ('get', self._list_url()),
            ('get', self._new_url()),
            ('get', self._edit_url(ep.id)),
            ('post', self._deactivate_url(ep.id)),
            ('post', self._test_url()),
        ]
        for method, url in cases:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                # domain_admin_required redirects rather than returning 403.
                self.assertRedirects(
                    response, reverse('homepage'), fetch_redirect_response=False
                )
        ep.refresh_from_db()
        assert ep.is_active


class TestCaseSearchEndpointsListView(EndpointViewTestCase):
    def test_empty_list(self):
        response = self.client.get(self._list_url())
        assert response.status_code == 200
        self.assertQuerySetEqual(response.context['endpoints'], [])

    def test_lists_active_endpoints(self):
        ep = self._make_endpoint()
        response = self.client.get(self._list_url())
        assert response.status_code == 200
        assert ep in response.context['endpoints']

    def test_new_endpoint_button_per_target_type(self):
        response = self.client.get(self._list_url())
        content = response.content.decode()
        for target_type in CaseSearchEndpoint.TargetType:
            assert f'?target_type={target_type.value}' in content
            assert f'New Endpoint ({target_type.label})' in content

    def test_inactive_endpoints_not_shown(self):
        ep = self._make_endpoint()
        ep.is_active = False
        ep.save(update_fields=['is_active'])
        response = self.client.get(self._list_url())
        assert ep not in response.context['endpoints']


class TestCaseSearchEndpointNewView(EndpointViewTestCase):
    def test_get(self):
        response = self.client.get(self._new_url())
        assert response.status_code == 200
        assert response.context['endpoint_mode'] == 'new'
        assert 'capability' in response.context
        # Defaults are seeded on the form (read via form.<field>.value).
        form = response.context['form']
        assert json.loads(form['query'].value()) == EMPTY_QUERY

    def test_target_type_comes_from_querystring(self):
        cases = [
            ('project_db', CaseSearchEndpoint.TargetType.PROJECT_DB),
            ('es', CaseSearchEndpoint.TargetType.ELASTICSEARCH),
        ]
        for param, expected in cases:
            with self.subTest(param=param):
                response = self.client.get(self._new_url(target_type=param))
                assert response.status_code == 200
                assert response.context['target_type'] == expected

    def test_invalid_target_type_404s(self):
        for param in ['bogus', None]:
            with self.subTest(param=param):
                response = self.client.get(self._new_url(target_type=param))
                assert response.status_code == 404

    def test_create_project_db_endpoint(self):
        with self._project_db_table():
            response = self.client.post(
                self._new_url(target_type='project_db'),
                self._post_data(
                    name='sql-endpoint',
                    sql='SELECT case_id FROM my_case_type',
                    # Elasticsearch fields are dropped, not validated, so a
                    # spec Elasticsearch would reject does not block the save
                    case_type='my_case_type',
                    query=json.dumps({'type': 'bogus'}),
                ),
            )
        assert response.status_code == 302
        endpoint = CaseSearchEndpoint.objects.get(
            domain=self.domain, name='sql-endpoint'
        )
        assert endpoint.target_type == CaseSearchEndpoint.TargetType.PROJECT_DB
        version = endpoint.current_version
        # The user's input is stored verbatim
        assert version.dangerous_sql == 'SELECT case_id FROM my_case_type'
        # ...and nothing belonging to an Elasticsearch endpoint is kept
        assert version.case_type is None
        assert version.query is None

    def test_elasticsearch_endpoint_does_not_store_sql(self):
        self.client.post(
            self._new_url(),
            self._post_data(name='es-endpoint', sql='DROP TABLE my_case_type'),
        )
        endpoint = CaseSearchEndpoint.objects.get(
            domain=self.domain, name='es-endpoint'
        )
        assert endpoint.current_version.dangerous_sql == ''

    def _save_sql(self, sql, parameters):
        with self._project_db_table():
            return self.client.post(
                self._new_url(target_type='project_db'),
                self._post_data(
                    name='sql-endpoint',
                    sql=sql,
                    parameters=json.dumps(parameters),
                ),
            )

    def test_sql_parameters_are_checked_against_the_spec(self):
        response = self._save_sql(
            'SELECT case_id FROM my_case_type WHERE prop__nickname = :who',
            [{'name': 'somebody_else', 'type': 'text'}],
        )
        assert response.status_code == 200
        errors = response.context['form'].errors['sql']
        assert any("Undefined parameter ':who'" in e for e in errors), errors
        assert any("':somebody_else' is not used" in e for e in errors), errors
        assert not CaseSearchEndpoint.objects.filter(
            domain=self.domain, name='sql-endpoint').exists()

    def test_declared_parameters_may_be_saved(self):
        response = self._save_sql(
            'SELECT case_id FROM my_case_type '
            'WHERE (:who IS NULL OR prop__nickname = :who) '
            'AND (:tags IS NULL OR select_prop__tags && :tags) '
            'AND (:seen_from IS NULL OR prop__nickname > :seen_from) '
            'AND (:seen_to IS NULL OR prop__nickname < :seen_to)',
            [
                {'name': 'who', 'type': 'text'},
                {'name': 'tags', 'type': 'select'},
                {'name': 'seen', 'type': 'daterange'},
            ],
        )
        assert response.status_code == 302, response.context['form'].errors

    def test_select_parameter_must_be_compared_with_an_array_column(self):
        response = self._save_sql(
            'SELECT case_id FROM my_case_type WHERE prop__nickname = :tags',
            [{'name': 'tags', 'type': 'select'}],
        )
        assert response.status_code == 200
        errors = response.context['form'].errors['sql']
        assert any('select_prop__ column' in e for e in errors), errors

    def test_parameter_used_with_in_is_rejected(self):
        response = self._save_sql(
            'SELECT case_id FROM my_case_type WHERE prop__nickname IN :tags',
            [{'name': 'tags', 'type': 'select'}],
        )
        assert response.status_code == 200
        errors = response.context['form'].errors['sql']
        assert any('used with IN' in e for e in errors), errors

    def test_project_db_unavailable_is_not_the_authors_fault(self):
        # The engine falls back to the default database under DEBUG or
        # UNIT_TESTING, so the failure has to be injected to be reachable.
        cases = [
            ImproperlyConfigured("'project_db' database not defined"),
            OperationalError('connection refused', None, None),
        ]
        for error in cases:
            with self.subTest(error=type(error).__name__), patch(
                'corehq.apps.project_db.user_sql.get_domain_tables',
                side_effect=error,
            ):
                response = self.client.post(
                    self._new_url(target_type='project_db'),
                    self._post_data(
                        name='sql-endpoint',
                        sql='SELECT case_id FROM my_case_type',
                    ),
                )
                assert response.status_code == 200
                form = response.context['form']
                assert 'unavailable' in form.non_field_errors()[0]
                # The author keeps what they wrote
                assert form['sql'].value() == 'SELECT case_id FROM my_case_type'
        assert not CaseSearchEndpoint.objects.filter(
            domain=self.domain, name='sql-endpoint'
        ).exists()

    def test_project_db_sql_errors(self):
        cases = [
            ('', 'SQL is required.'),
            ('DELETE FROM my_case_type', 'unsupported statement'),
            ('SELECT nope FROM my_case_type', 'unknown column'),
            ('SELECT case_id FROM no_such_table', 'unknown table'),
        ]
        for sql, expected in cases:
            with self.subTest(sql=sql), self._project_db_table():
                response = self.client.post(
                    self._new_url(target_type='project_db'),
                    self._post_data(name='bad-sql', case_type='', sql=sql),
                )
                assert response.status_code == 200
                errors = response.context['form'].errors['sql']
                assert expected in errors[0]
                assert errors[0] in response.content.decode()
        assert not CaseSearchEndpoint.objects.filter(
            domain=self.domain, name='bad-sql'
        ).exists()

    def test_create_endpoint(self):
        response = self.client.post(
            self._new_url(),
            self._post_data(
                name='new-endpoint',
                case_type='my_case_type',
            ),
        )
        assert response.status_code == 302
        endpoint = CaseSearchEndpoint.objects.get(
            domain=self.domain, name='new-endpoint'
        )
        assert endpoint.target_type == CaseSearchEndpoint.TargetType.ELASTICSEARCH
        assert endpoint.current_version.case_type == 'my_case_type'
        assert endpoint.current_version is not None
        assert endpoint.current_version.version_number == 1
        assert endpoint.current_version.query == EMPTY_QUERY
        assert (
            endpoint.current_version.action
            == CaseSearchEndpointVersion.Action.CREATE
        )
        assert endpoint.current_version.created_by == self.username

    def test_create_with_empty_query_defaults_to_empty_group(self):
        self.client.post(
            self._new_url(),
            self._post_data(
                name='ep-empty-query',
                query='',
                parameters='',
            ),
        )
        endpoint = CaseSearchEndpoint.objects.get(
            domain=self.domain, name='ep-empty-query'
        )
        assert endpoint.current_version.query == EMPTY_QUERY
        assert endpoint.current_version.parameters == []

    def test_duplicate_name_error(self):
        self._make_endpoint(name='existing')
        response = self.client.post(
            self._new_url(), self._post_data(name='existing')
        )
        assert response.status_code == 200
        error = response.context['form'].errors['name'][0]
        assert 'already exists' in error
        content = response.content.decode()
        # Bootstrap only reveals .invalid-feedback next to .is-invalid
        assert 'form-control is-invalid' in content
        assert escape(error) in content

    def test_form_field_validation_error(self):
        cases = [
            ({'query': 'not json'}, 'query', None),
            ({'query': '[1, 2]'}, 'query', 'JSON object'),
            ({'parameters': '{"not": "array"}'}, 'parameters', 'JSON array'),
        ]
        for overrides, error_field, error_fragment in cases:
            with self.subTest(overrides=overrides):
                response = self.client.post(self._new_url(), self._post_data(**overrides))
                assert response.status_code == 200
                errors = response.context['form'].errors
                assert error_field in errors
                if error_fragment:
                    assert error_fragment in errors[error_field][0]

    def test_invalid_query_spec_rejected(self):
        # An unknown node type surfaces as a non-field (semantic) error.
        response = self.client.post(
            self._new_url(),
            self._post_data(
                query=json.dumps({'type': 'bogus'}),
            ),
        )
        assert response.status_code == 200
        assert response.context['form'].non_field_errors()
        assert not CaseSearchEndpoint.objects.filter(
            domain=self.domain, name='an-endpoint'
        ).exists()

    def test_failed_post_preserves_submitted_query(self):
        # Re-render seeds the query builder from the submitted (not DB) values.
        submitted = {'type': 'any', 'children': []}
        response = self.client.post(
            self._new_url(),
            self._post_data(
                name='',  # triggers a validation error
                query=json.dumps(submitted),
            ),
        )
        assert response.status_code == 200
        form = response.context['form']
        assert json.loads(form['query'].value()) == submitted


class TestCaseSearchEndpointEditView(EndpointViewTestCase):
    def test_project_db_endpoint_seeds_sql_from_current_version(self):
        ep = self._make_endpoint(
            target_type=CaseSearchEndpoint.TargetType.PROJECT_DB
        )
        version = ep.current_version
        version.dangerous_sql = 'SELECT case_id FROM my_case_type'
        version.save(update_fields=['dangerous_sql'])
        response = self.client.get(self._edit_url(ep.id))
        form = response.context['form']
        assert form['sql'].value() == 'SELECT case_id FROM my_case_type'

    def test_edit_project_db_endpoint_versions_sql(self):
        ep = self._make_endpoint(
            target_type=CaseSearchEndpoint.TargetType.PROJECT_DB
        )
        with self._project_db_table():
            response = self.client.post(
                self._edit_url(ep.id),
                self._post_data(
                    name=ep.name,
                    case_type='',
                    sql='SELECT case_name FROM my_case_type',
                ),
            )
        assert response.status_code == 302
        ep.refresh_from_db()
        assert ep.current_version.version_number == 2
        assert ep.current_version.dangerous_sql == (
            'SELECT case_name FROM my_case_type'
        )

    def test_get(self):
        ep = self._make_endpoint()
        response = self.client.get(self._edit_url(ep.id))
        assert response.status_code == 200
        assert response.context['endpoint'] == ep
        assert response.context['endpoint_mode'] == 'edit'
        # Scalar fields are seeded on the form (read via form.<field>.value).
        form = response.context['form']
        assert form['name'].value() == ep.name
        assert form['case_type'].value() == ep.current_version.case_type

    def test_404_for_wrong_domain(self):
        ep = self._make_endpoint()
        url = reverse(
            CaseSearchEndpointEditView.urlname, args=['other-domain', ep.id]
        )
        response = self.client.get(url)
        assert response.status_code == 404

    def test_404_for_inactive_endpoint(self):
        ep = self._make_endpoint()
        ep.is_active = False
        ep.save(update_fields=['is_active'])
        response = self.client.get(self._edit_url(ep.id))
        assert response.status_code == 404

    def test_edit_creates_new_version(self):
        ep = self._make_endpoint()
        new_query = {'type': 'any', 'children': []}
        response = self.client.post(
            self._edit_url(ep.id),
            self._post_data(
                name=ep.name,
                case_type=ep.current_version.case_type,
                query=json.dumps(new_query),
                parameters='[]',
            ),
        )
        assert response.status_code == 302
        ep.refresh_from_db()
        assert ep.current_version.version_number == 2
        assert ep.current_version.query == new_query
        assert ep.current_version.parameters == []
        assert (
            ep.current_version.action
            == CaseSearchEndpointVersion.Action.UPDATE
        )
        assert ep.current_version.created_by == self.username
        assert ep.versions.count() == 2

    def test_edit_updates_endpoint_fields(self):
        ep = self._make_endpoint()
        self.client.post(
            self._edit_url(ep.id),
            self._post_data(
                name='renamed',
                case_type='new_target',
            ),
        )
        ep.refresh_from_db()
        assert ep.name == 'renamed'
        assert ep.current_version.case_type == 'new_target'

    def test_duplicate_name_error(self):
        self._make_endpoint(name='ep1')
        ep2 = self._make_endpoint(name='ep2')
        response = self.client.post(
            self._edit_url(ep2.id),
            self._post_data(
                name='ep1',
                case_type=ep2.current_version.case_type,
            ),
        )
        assert response.status_code == 200
        assert 'already exists' in response.context['form'].errors['name'][0]

    def test_can_keep_same_name_on_edit(self):
        ep = self._make_endpoint(name='my-ep')
        response = self.client.post(
            self._edit_url(ep.id),
            self._post_data(
                name='my-ep',
                case_type=ep.current_version.case_type,
            ),
        )
        assert response.status_code == 302


class TestCaseSearchEndpointDeactivateView(EndpointViewTestCase):
    def test_deactivates_endpoint(self):
        ep = self._make_endpoint()
        response = self.client.post(self._deactivate_url(ep.id))
        self.assertRedirects(response, self._list_url())
        ep.refresh_from_db()
        assert not ep.is_active
        assert ep.current_version is not None
        assert (
            ep.current_version.action
            == CaseSearchEndpointVersion.Action.DEACTIVATE
        )
        assert ep.current_version.created_by == self.username
        assert ep.current_version.case_type is None
        assert ep.current_version.query is None
        assert ep.current_version.parameters is None
        assert ep.versions.count() == 2

    def test_404_for_wrong_domain(self):
        ep = self._make_endpoint()
        url = reverse(
            CaseSearchEndpointDeactivateView.urlname,
            args=['other-domain', ep.id],
        )
        response = self.client.post(url)
        assert response.status_code == 404

    def test_404_for_already_inactive(self):
        ep = self._make_endpoint()
        ep.is_active = False
        ep.save(update_fields=['is_active'])
        response = self.client.post(self._deactivate_url(ep.id))
        assert response.status_code == 404


class TestCaseSearchEndpointTestView(EndpointViewTestCase):
    def test_valid_query_returns_no_errors(self):
        with patch('corehq.apps.case_search.endpoint_views.get_primary_case_search_endpoint_results',
                   return_value=[]):
            response = self.client.post(self._test_url(), {
                'case_type': 'my_case_type',
                'query': json.dumps(EMPTY_QUERY),
            })
        assert response.status_code == 200
        assert 'alert-danger' not in response.content.decode()

    def test_invalid_query_returns_error(self):
        cases = [
            ('not json', 'Invalid query JSON'),
            (json.dumps({'type': 'bogus'}), 'alert-danger'),
        ]
        for query, expected_text in cases:
            with self.subTest(query=query):
                response = self.client.post(self._test_url(), {
                    'case_type': 'my_case_type',
                    'query': query,
                })
                assert response.status_code == 200
                content = response.content.decode()
                assert expected_text in content
                assert '<table' not in content

    def test_unknown_case_type_returns_error(self):
        response = self.client.post(self._test_url(), {
            'case_type': 'nonexistent_type',
            'query': json.dumps(EMPTY_QUERY),
        })
        assert response.status_code == 200
        content = response.content.decode()
        assert 'alert-danger' in content
        assert '<table' not in content

    def test_missing_case_type_returns_error(self):
        response = self.client.post(self._test_url(), {
            'query': json.dumps(EMPTY_QUERY),
        })
        assert response.status_code == 200
        assert 'alert-danger' in response.content.decode()

    def test_requires_post(self):
        response = self.client.get(self._test_url())
        assert response.status_code == 405


# ── matching a parameter spec against the SQL that binds it ──────────────────

def _binds(**types):
    """Stand in for ``UserSQL.parameter_binds``: a bind per placeholder"""
    return {
        name: bindparam(name, type_=type_, expanding=(type_ == 'expanding'))
        for name, type_ in types.items()
    }


TEXT_PARAM = Parameter(name='color', type=FIELD_TYPE_TEXT)
SELECT_PARAM = Parameter(name='species', type=FIELD_TYPE_SELECT)
RANGE_PARAM = Parameter(name='dob', type=FIELD_TYPE_DATERANGE)


@pytest.mark.parametrize('binds, parameters', [
    ({}, []),
    (_binds(color=Text()), [TEXT_PARAM]),
    (_binds(species=ARRAY(Text())), [SELECT_PARAM]),
    (_binds(dob_from=Text(), dob_to=Text()), [RANGE_PARAM]),
    # A parameter only ever compared with NULL says nothing about its shape
    (_binds(species=None), [SELECT_PARAM]),
])
def test_sql_parameter_errors_accepts(binds, parameters):
    assert list(sql_parameter_errors(binds, parameters)) == []


@pytest.mark.parametrize('binds, parameters, error_fragment', [
    (_binds(color=Text()), [], "Undefined parameter ':color'"),
    ({}, [TEXT_PARAM], "Parameter ':color' is not used by the SQL"),
    # A date range must be bound by both of its derived names
    (_binds(dob_from=Text()), [RANGE_PARAM], "Parameter ':dob_to' is not used"),
    (_binds(color='expanding'), [TEXT_PARAM], "used with IN, which is not supported"),
    (_binds(species=Text()), [SELECT_PARAM], "must be compared with a select_prop__ column"),
    (_binds(color=ARRAY(Text())), [TEXT_PARAM], "must be declared as a select parameter"),
])
def test_sql_parameter_errors_reports(binds, parameters, error_fragment):
    errors = list(sql_parameter_errors(binds, parameters))
    assert any(error_fragment in e for e in errors), errors
