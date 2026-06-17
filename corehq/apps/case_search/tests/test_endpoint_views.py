import json

from django.test import TestCase
from django.urls import reverse

from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled

from ..endpoint_views import (
    CaseSearchEndpointDeactivateView,
    CaseSearchEndpointEditView,
    CaseSearchEndpointNewView,
    CaseSearchEndpointsView,
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

    def _make_endpoint(self, name='my-endpoint', target_name='case_type_a'):
        endpoint = CaseSearchEndpoint.objects.create(
            domain=self.domain,
            name=name,
            target_name=target_name,
        )
        version = CaseSearchEndpointVersion.objects.create(
            endpoint=endpoint,
            version_number=1,
            query=dict(EMPTY_QUERY),
            parameters=[],
            action=CaseSearchEndpointVersion.Action.CREATE,
        )
        endpoint.current_version = version
        endpoint.save(update_fields=['current_version'])
        return endpoint

    def _list_url(self):
        return reverse(CaseSearchEndpointsView.urlname, args=[self.domain])

    def _new_url(self):
        return reverse(CaseSearchEndpointNewView.urlname, args=[self.domain])

    def _edit_url(self, endpoint_id):
        return reverse(
            CaseSearchEndpointEditView.urlname, args=[self.domain, endpoint_id]
        )

    def _deactivate_url(self, endpoint_id):
        return reverse(
            CaseSearchEndpointDeactivateView.urlname,
            args=[self.domain, endpoint_id],
        )

    def _post_data(self, **overrides):
        data = {
            'name': 'an-endpoint',
            'target_type': CaseSearchEndpoint.TargetType.PROJECT_DB,
            'case_type': 'my_case_type',
            'query': json.dumps(EMPTY_QUERY),
            'parameters': '[]',
        }
        data.update(overrides)
        return data


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
        assert response.context['initial_query'] == EMPTY_QUERY
        assert 'capability' in response.context
        # target_type default is seeded on the form (read via form.<field>.value).
        form = response.context['form']
        assert form['target_type'].value() == (
            CaseSearchEndpoint.TargetType.PROJECT_DB
        )

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
        assert endpoint.target_name == 'my_case_type'
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
        assert 'already exists' in response.context['form'].errors['name'][0]

    def test_invalid_query_json_error(self):
        response = self.client.post(
            self._new_url(), self._post_data(query='not json')
        )
        assert response.status_code == 200
        assert 'query' in response.context['form'].errors

    def test_query_must_be_object_not_array(self):
        response = self.client.post(
            self._new_url(), self._post_data(query='[1, 2]')
        )
        assert response.status_code == 200
        assert 'JSON object' in response.context['form'].errors['query'][0]

    def test_parameters_must_be_array(self):
        response = self.client.post(
            self._new_url(), self._post_data(parameters='{"not": "array"}')
        )
        assert response.status_code == 200
        assert 'JSON array' in response.context['form'].errors['parameters'][0]

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
        assert response.context['initial_query'] == submitted


class TestCaseSearchEndpointEditView(EndpointViewTestCase):
    def test_get(self):
        ep = self._make_endpoint()
        response = self.client.get(self._edit_url(ep.id))
        assert response.status_code == 200
        assert response.context['endpoint'] == ep
        assert response.context['endpoint_mode'] == 'edit'
        # Scalar fields are seeded on the form (read via form.<field>.value).
        form = response.context['form']
        assert form['name'].value() == ep.name
        assert form['case_type'].value() == ep.target_name

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
                case_type=ep.target_name,
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
                target_type=CaseSearchEndpoint.TargetType.ELASTICSEARCH,
                case_type='new_target',
            ),
        )
        ep.refresh_from_db()
        assert ep.name == 'renamed'
        assert ep.target_type == CaseSearchEndpoint.TargetType.ELASTICSEARCH
        assert ep.target_name == 'new_target'

    def test_duplicate_name_error(self):
        self._make_endpoint(name='ep1')
        ep2 = self._make_endpoint(name='ep2')
        response = self.client.post(
            self._edit_url(ep2.id),
            self._post_data(
                name='ep1',
                case_type=ep2.target_name,
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
                case_type=ep.target_name,
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
