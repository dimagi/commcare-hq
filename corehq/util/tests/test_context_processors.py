from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory, override_settings

from ..context_processors import js_api_keys, server_location_display


class FakeCouchUser:
    def __init__(self, analytics_enabled):
        self.analytics_enabled = analytics_enabled


class FakeProject:
    def __init__(self, ga_opt_out):
        self.ga_opt_out = ga_opt_out


def _mock_is_hubspot_js_allowed_for_request(request):
    return request.is_hubspot_js_allowed_for_request


@override_settings(ANALYTICS_IDS={
    'GOOGLE_ANALYTICS_API_ID': 'UA-for-tests-only',
    'HUBSPOT_API_ID': 'test_api_id',
    'HUBSPOT_ACCESS_TOKEN': 'test_api_key',
})
class TestJsApiKeys(SimpleTestCase):

    def test_blocked_couch_user_returns_nothing(self):
        blocked_request = RequestFactory().get('/test')
        blocked_request.couch_user = FakeCouchUser(False)
        self.assertEqual(js_api_keys(blocked_request), {})

    def test_settings_is_not_mutated_when_google_analytics_is_deleted(self):
        normal_request = RequestFactory().get('/test')
        blocked_request = RequestFactory().get('/test')
        blocked_request.project = FakeProject(True)
        self.assertIsNone(js_api_keys(blocked_request)['ANALYTICS_IDS'].get('GOOGLE_ANALYTICS_API_ID'))
        self.assertIsNotNone(js_api_keys(normal_request)['ANALYTICS_IDS'].get('GOOGLE_ANALYTICS_API_ID'))

    @patch(
        'corehq.util.context_processors.is_hubspot_js_allowed_for_request',
        _mock_is_hubspot_js_allowed_for_request
    )
    def test_settings_is_not_mutated_when_hubspot_analytics_is_deleted(self):
        normal_request = RequestFactory().get('/test')
        normal_request.is_hubspot_js_allowed_for_request = True

        blocked_request = RequestFactory().get('/test')
        blocked_request.is_hubspot_js_allowed_for_request = False

        blocked_js_keys = js_api_keys(blocked_request)
        self.assertEqual(blocked_js_keys['ANALYTICS_IDS'].get('HUBSPOT_API_ID'), '')
        self.assertEqual(blocked_js_keys['ANALYTICS_IDS'].get('HUBSPOT_ACCESS_TOKEN'), '')

        normal_js_keys = js_api_keys(blocked_request)
        self.assertIsNotNone(normal_js_keys['ANALYTICS_IDS'].get('HUBSPOT_API_ID'))
        self.assertIsNotNone(normal_js_keys['ANALYTICS_IDS'].get('HUBSPOT_ACCESS_TOKEN'))


class TestServerLocationDisplay(SimpleTestCase):

    @override_settings(SERVER_ENVIRONMENT='production')
    def test_environment_in_display_options(self):
        request = RequestFactory().get('/test')
        context = server_location_display(request)
        expected_context = {
            'server_display': {
                'flag': "🇺🇸",
                'hr_name': "US",
            },
        }
        self.assertEqual(context, expected_context)

    @override_settings(SERVER_ENVIRONMENT='notarealserver')
    def test_environment_not_in_display_options(self):
        request = RequestFactory().get('/test')
        context = server_location_display(request)
        expected_context = {}
        self.assertEqual(context, expected_context)
