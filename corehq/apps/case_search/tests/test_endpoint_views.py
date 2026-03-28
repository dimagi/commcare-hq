import json

from django.test import TestCase
from django.urls import reverse

from corehq import toggles
from corehq.apps.case_search.endpoint_service import create_endpoint
from corehq.apps.data_dictionary.models import CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser


DOMAIN = 'test-endpoint-views'
USERNAME = 'endpoint-view-user@test.com'
PASSWORD = 'password'
CASE_TYPE = 'patient'


class EndpointViewTestCase(TestCase):
    """Base class providing domain, user, toggle, and logged-in client."""

    @classmethod
    def setUpTestData(cls):
        cls.domain_obj = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(
            DOMAIN, USERNAME, PASSWORD, None, None, is_admin=True
        )
        cls.addClassCleanup(cls.user.delete, DOMAIN, None)
        cls.case_type = CaseType.objects.create(domain=DOMAIN, name=CASE_TYPE)
        cls.addClassCleanup(cls.case_type.delete)

    def setUp(self):
        toggles.CASE_SEARCH_ENDPOINTS.set(
            DOMAIN, True, namespace=toggles.NAMESPACE_DOMAIN
        )
        self.addCleanup(
            toggles.CASE_SEARCH_ENDPOINTS.set,
            DOMAIN,
            False,
            namespace=toggles.NAMESPACE_DOMAIN,
        )
        self.client.login(username=USERNAME, password=PASSWORD)

    def _make_endpoint(self, name='Test Endpoint', target_name=CASE_TYPE):
        return create_endpoint(
            domain=DOMAIN,
            name=name,
            target_type='project_db',
            target_name=target_name,
            parameters=[],
            query={'type': 'and', 'children': []},
        )


class TestCaseSearchEndpointsView(EndpointViewTestCase):
    def _url(self):
        return reverse('case_search_endpoints', args=[DOMAIN])

    def test_returns_200_with_endpoints_in_context(self):
        response = self.client.get(self._url())
        assert response.status_code == 200
        assert 'endpoints' in response.context

    def test_returns_404_when_toggle_disabled(self):
        toggles.CASE_SEARCH_ENDPOINTS.set(
            DOMAIN, False, namespace=toggles.NAMESPACE_DOMAIN
        )
        response = self.client.get(self._url())
        assert response.status_code == 404

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self._url())
        assert response.status_code == 302
        assert (
            '/accounts/login/' in response['Location']
            or 'login' in response['Location']
        )


class TestCaseSearchEndpointNewView(EndpointViewTestCase):
    def _url(self):
        return reverse('case_search_endpoint_new', args=[DOMAIN])

    def test_get_returns_200_with_expected_context_keys(self):
        response = self.client.get(self._url())
        assert response.status_code == 200
        ctx = response.context
        for key in (
            'capability',
            'mode',
            'initial_parameters',
            'initial_query',
            'initial_target_name',
            'initial_name',
            'versions',
            'post_url',
        ):
            assert key in ctx, f'Missing context key: {key}'

    def test_post_valid_data_creates_endpoint_and_redirects(self):
        data = {
            'name': 'New Endpoint',
            'target_type': 'project_db',
            'target_name': CASE_TYPE,
            'parameters': [],
            'query': {'type': 'and', 'children': []},
        }
        response = self.client.post(
            self._url(),
            data=json.dumps(data),
            content_type='application/json',
        )
        assert response.status_code == 200
        body = json.loads(response.content)
        assert 'redirect' in body

    def test_post_empty_name_returns_400_with_errors(self):
        data = {
            'name': '',
            'target_type': 'project_db',
            'target_name': 'patient',
            'parameters': [],
            'query': {'type': 'and', 'children': []},
        }
        response = self.client.post(
            self._url(),
            data=json.dumps(data),
            content_type='application/json',
        )
        assert response.status_code == 400
        body = json.loads(response.content)
        assert 'errors' in body
        assert len(body['errors']) > 0

    def test_post_missing_case_type_returns_400(self):
        data = {
            'name': 'Missing Case Type',
            'target_type': 'project_db',
            'target_name': '',
            'parameters': [],
            'query': {'type': 'and', 'children': []},
        }
        response = self.client.post(
            self._url(),
            data=json.dumps(data),
            content_type='application/json',
        )
        assert response.status_code == 400
        body = json.loads(response.content)
        assert 'errors' in body


class TestCaseSearchEndpointEditView(EndpointViewTestCase):
    def _url(self, endpoint_id):
        return reverse('case_search_endpoint_edit', args=[DOMAIN, endpoint_id])

    def test_get_returns_200_for_existing_endpoint(self):
        endpoint = self._make_endpoint('Edit Me')
        response = self.client.get(self._url(endpoint.id))
        assert response.status_code == 200

    def test_get_returns_404_for_nonexistent_endpoint(self):
        response = self.client.get(self._url(999999))
        assert response.status_code == 404

    def test_post_valid_data_creates_new_version(self):
        endpoint = self._make_endpoint('Version Me')
        data = {
            'parameters': [],
            'query': {'type': 'and', 'children': []},
        }
        response = self.client.post(
            self._url(endpoint.id),
            data=json.dumps(data),
            content_type='application/json',
        )
        assert response.status_code == 200
        body = json.loads(response.content)
        assert 'redirect' in body
        assert 'version_number' in body
        assert body['version_number'] == 2

    def test_post_invalid_query_returns_400(self):
        endpoint = self._make_endpoint('Bad Query')
        data = {
            'parameters': [],
            'query': {'type': 'unknown_type', 'children': []},
        }
        response = self.client.post(
            self._url(endpoint.id),
            data=json.dumps(data),
            content_type='application/json',
        )
        assert response.status_code == 400
        body = json.loads(response.content)
        assert 'errors' in body


class TestCaseSearchEndpointDeactivateView(EndpointViewTestCase):
    def _url(self, endpoint_id):
        return reverse(
            'case_search_endpoint_deactivate', args=[DOMAIN, endpoint_id]
        )

    def test_post_deactivates_endpoint_and_redirects(self):
        endpoint = self._make_endpoint('Deactivate Me')
        response = self.client.post(self._url(endpoint.id))
        assert response.status_code == 200
        body = json.loads(response.content)
        assert 'redirect' in body
        endpoint.refresh_from_db()
        assert endpoint.is_active is False

    def test_post_returns_404_for_nonexistent_endpoint(self):
        response = self.client.post(self._url(999999))
        assert response.status_code == 404


class TestCaseSearchCapabilityView(EndpointViewTestCase):
    def _url(self):
        return reverse('case_search_capability', args=[DOMAIN])

    def test_get_returns_200_json_response(self):
        response = self.client.get(self._url())
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
        body = json.loads(response.content)
        assert 'case_types' in body
        assert 'auto_values' in body
        assert 'component_input_schemas' in body
