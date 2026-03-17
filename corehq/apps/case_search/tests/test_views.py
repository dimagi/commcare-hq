import json

from django.urls import reverse

from corehq.apps.case_search import endpoint_service
from corehq.apps.case_search.models import CaseSearchEndpoint
from corehq.apps.case_search.views.endpoints import (
    CaseSearchCapabilityView,
    CaseSearchEndpointDeactivateView,
    CaseSearchEndpointEditView,
    CaseSearchEndpointNewView,
    CaseSearchEndpointsView,
    CaseSearchEndpointVersionView,
)
from corehq.tests.util.htmx import HtmxViewTestCase
from corehq.util.test_utils import flag_enabled

from ..models import CSQLFixtureExpression, CSQLFixtureExpressionLog
from ..views.base import CSQLFixtureExpressionView

EMPTY_QUERY = {'type': 'and', 'children': []}
SAMPLE_PARAMS = [{'name': 'province', 'type': 'text'}]


@flag_enabled('CSQL_FIXTURE')
class TestCSQLFixtureExpressionView(HtmxViewTestCase):
    def get_url(self):
        return reverse(CSQLFixtureExpressionView.urlname, args=[self.domain])

    def test_create_update_delete(self):
        # create
        response = self.hx_action(
            'save_expression',
            {
                'name': 'my_indicator_name',
                'csql': 'original csql',
            },
        )
        self.assertEqual(response.status_code, 200)
        expression = CSQLFixtureExpression.objects.get(
            domain=self.domain, name='my_indicator_name'
        )
        self.assertEqual(expression.csql, 'original csql')

        # update
        response = self.hx_action(
            'save_expression',
            {
                'pk': expression.pk,
                'name': expression.name,
                'csql': 'updated csql',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            CSQLFixtureExpression.objects.get(pk=expression.pk).csql,
            'updated csql',
        )

        # delete
        response = self.hx_action('delete_expression', {'pk': expression.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            CSQLFixtureExpression.objects.get(pk=expression.pk).deleted
        )

        # check log
        self.assertEqual(
            list(
                expression.csqlfixtureexpressionlog_set.values_list(
                    'action', 'csql'
                )
            ),
            [
                (
                    CSQLFixtureExpressionLog.Action.CREATE.value,
                    'original csql',
                ),
                (CSQLFixtureExpressionLog.Action.UPDATE.value, 'updated csql'),
                (CSQLFixtureExpressionLog.Action.DELETE.value, ''),
            ],
        )

    def test_new_criteria(self):
        response = self.hx_action('new_criteria', {})
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.content.decode())

    def test_save_filter_modal(self):
        expression = CSQLFixtureExpression.objects.create(
            domain=self.domain, name='my_indicator_name', csql='original csql'
        )
        response = self.hx_action(
            'save_filter_modal',
            {
                'pk': expression.pk,
                'operator': ['IS'],
                'property_name': ['my_property'],
            },
        )
        self.assertEqual(response.status_code, 200)

        expression.refresh_from_db()
        self.assertEqual(
            expression.user_data_criteria,
            [{'operator': 'IS', 'property_name': 'my_property'}],
        )


class EndpointViewTestCase(HtmxViewTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username=self.username, password='password')


@flag_enabled('CASE_SEARCH_ENDPOINTS')
class TestCaseSearchEndpointsListView(EndpointViewTestCase):
    def get_url(self):
        return reverse(CaseSearchEndpointsView.urlname, args=[self.domain])

    def test_list_empty(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_list_with_endpoints(self):
        endpoint_service.create_endpoint(
            self.domain, 'ep-1', 'project_db', 'patient', [], EMPTY_QUERY
        )
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ep-1')


@flag_enabled('CASE_SEARCH_ENDPOINTS')
class TestCaseSearchEndpointNewView(EndpointViewTestCase):
    def get_url(self):
        return reverse(CaseSearchEndpointNewView.urlname, args=[self.domain])

    def test_get_renders_form(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_post_creates_endpoint(self):
        response = self.client.post(
            self.get_url(),
            data=json.dumps(
                {
                    'name': 'find-patients',
                    'target_type': 'project_db',
                    'target_name': 'patient',
                    'parameters': SAMPLE_PARAMS,
                    'query': EMPTY_QUERY,
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        endpoint = CaseSearchEndpoint.objects.get(
            domain=self.domain, name='find-patients'
        )
        self.assertIsNotNone(endpoint.current_version)
        self.assertEqual(endpoint.current_version.version_number, 1)

    def test_post_returns_400_on_invalid_spec(self):
        response = self.client.post(
            self.get_url(),
            data=json.dumps(
                {
                    'name': 'bad-endpoint',
                    'target_type': 'project_db',
                    'target_name': 'patient',
                    'parameters': [],
                    'query': {'type': 'invalid'},
                }
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', json.loads(response.content))


@flag_enabled('CASE_SEARCH_ENDPOINTS')
class TestCaseSearchEndpointEditView(EndpointViewTestCase):
    def setUp(self):
        super().setUp()
        self.endpoint = endpoint_service.create_endpoint(
            self.domain,
            'ep-1',
            'project_db',
            'patient',
            [],
            EMPTY_QUERY,
        )

    def get_url(self):
        return reverse(
            CaseSearchEndpointEditView.urlname,
            args=[self.domain, self.endpoint.id],
        )

    def test_get_renders_edit_form(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)

    def test_post_creates_new_version(self):
        response = self.client.post(
            self.get_url(),
            data=json.dumps(
                {'parameters': SAMPLE_PARAMS, 'query': EMPTY_QUERY}
            ),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.current_version.version_number, 2)


@flag_enabled('CASE_SEARCH_ENDPOINTS')
class TestCaseSearchEndpointVersionView(EndpointViewTestCase):
    def setUp(self):
        super().setUp()
        self.endpoint = endpoint_service.create_endpoint(
            self.domain,
            'ep-1',
            'project_db',
            'patient',
            [],
            EMPTY_QUERY,
        )
        endpoint_service.save_new_version(
            self.endpoint, SAMPLE_PARAMS, EMPTY_QUERY
        )

    def get_url(self, version_number):
        return reverse(
            CaseSearchEndpointVersionView.urlname,
            args=[self.domain, self.endpoint.id, version_number],
        )

    def test_get_v1_renders(self):
        response = self.client.get(self.get_url(1))
        self.assertEqual(response.status_code, 200)

    def test_get_v2_renders(self):
        response = self.client.get(self.get_url(2))
        self.assertEqual(response.status_code, 200)

    def test_get_nonexistent_version_returns_404(self):
        response = self.client.get(self.get_url(99))
        self.assertEqual(response.status_code, 404)


@flag_enabled('CASE_SEARCH_ENDPOINTS')
class TestCaseSearchEndpointDeactivateView(EndpointViewTestCase):
    def setUp(self):
        super().setUp()
        self.endpoint = endpoint_service.create_endpoint(
            self.domain,
            'ep-1',
            'project_db',
            'patient',
            [],
            EMPTY_QUERY,
        )

    def get_url(self):
        return reverse(
            CaseSearchEndpointDeactivateView.urlname,
            args=[self.domain, self.endpoint.id],
        )

    def test_post_deactivates(self):
        response = self.client.post(self.get_url())
        self.assertEqual(response.status_code, 200)
        self.endpoint.refresh_from_db()
        self.assertFalse(self.endpoint.is_active)

    def test_post_returns_empty_response(self):
        response = self.client.post(self.get_url())
        self.assertEqual(response.content, b'')


@flag_enabled('CASE_SEARCH_ENDPOINTS')
class TestCaseSearchCapabilityView(EndpointViewTestCase):
    def get_url(self):
        return reverse(CaseSearchCapabilityView.urlname, args=[self.domain])

    def test_get_returns_json(self):
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('case_types', data)
        self.assertIn('auto_values', data)
        self.assertIn('component_input_schemas', data)
