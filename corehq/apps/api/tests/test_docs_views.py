import json

from django.test import Client, SimpleTestCase, TestCase

from corehq.apps.api.docs_views import with_host


class TestWithHost(SimpleTestCase):
    def test_substitutes_the_host_default(self):
        spec = {
            'servers': [
                {
                    'url': 'https://{host}',
                    'variables': {
                        'host': {
                            'default': 'www.commcarehq.org',
                            'description': 'Hostname of the CommCare HQ instance.',
                        }
                    },
                }
            ],
        }
        result = with_host(spec, 'hq.example.org')
        variables = result['servers'][0]['variables']['host']
        assert variables['default'] == 'hq.example.org'
        assert variables['description'] == (
            'Hostname of the CommCare HQ instance.'
        )

    def test_does_not_mutate_the_input(self):
        spec = {
            'servers': [
                {
                    'url': 'https://{host}',
                    'variables': {'host': {'default': 'www.commcarehq.org'}},
                }
            ],
        }
        with_host(spec, 'hq.example.org')
        assert (
            spec['servers'][0]['variables']['host']['default']
            == 'www.commcarehq.org'
        )

    def test_spec_without_servers_is_returned_unchanged(self):
        assert with_host({'openapi': '3.0.3'}, 'x') == {'openapi': '3.0.3'}


class TestSpecEndpoints(TestCase):
    def setUp(self):
        self.client = Client()

    def test_bundle_is_served_anonymously(self):
        response = self.client.get('/api/openapi.json')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
        assert json.loads(response.content)['openapi'] == '3.0.3'

    def test_servers_default_is_the_requesting_host(self):
        response = self.client.get(
            '/api/openapi.json', HTTP_HOST='hq.example.org'
        )
        document = json.loads(response.content)
        host = document['servers'][0]['variables']['host']['default']
        assert host == 'hq.example.org'

    def test_cors_headers_are_present(self):
        response = self.client.get('/api/openapi.json')
        assert response['Access-Control-Allow-Origin'] == '*'

    def test_etag_is_stable_per_host_and_differs_across_hosts(self):
        first = self.client.get('/api/openapi.json', HTTP_HOST='a.example.org')
        again = self.client.get('/api/openapi.json', HTTP_HOST='a.example.org')
        other = self.client.get('/api/openapi.json', HTTP_HOST='b.example.org')
        assert first['ETag'] == again['ETag']
        assert first['ETag'] != other['ETag']

    def test_per_api_spec_is_served(self):
        response = self.client.get('/api/docs/user-v1/openapi.json')
        assert response.status_code == 200
        document = json.loads(response.content)
        assert '/a/{domain}/api/user/v1/' in document['paths']

    def test_unknown_slug_is_404(self):
        response = self.client.get('/api/docs/not-a-real-api/openapi.json')
        assert response.status_code == 404

    def test_well_known_alias_serves_the_bundle(self):
        alias = self.client.get('/.well-known/openapi.json')
        canonical = self.client.get('/api/openapi.json')
        assert alias.status_code == 200
        assert alias.content == canonical.content

    def test_user_scoped_api_still_resolves(self):
        # The docs URLs are registered ahead of the user-scoped resources under
        # the same /api/ prefix; this asserts they did not shadow them.
        from django.urls import resolve

        match = resolve('/api/identity/v1/')
        assert match.kwargs.get('resource_name') == 'identity'
