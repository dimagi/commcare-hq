import json
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase

from corehq.apps.api.docs_views import with_host
from corehq.apps.api.openapi import artifacts


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


class TestDocsIndex(TestCase):

    def setUp(self):
        self.client = Client()

    def test_index_is_served_anonymously(self):
        response = self.client.get('/api/docs/')
        assert response.status_code == 200

    def test_index_lists_every_documented_api(self):
        from corehq.apps.api.openapi.artifacts import documented_slugs

        content = self.client.get('/api/docs/').content.decode()
        for slug in documented_slugs():
            assert f'/api/docs/{slug}/' in content, slug

    def test_index_marks_each_coverage_state(self):
        # One API per coverage state, so a hard-coded count can't drift out
        # from under the assertions -- the numbers below are derived from
        # the specs themselves.
        full_described, full_total = artifacts.description_coverage(
            'user-v1'
        )
        partial_described, partial_total = artifacts.description_coverage(
            'web-user-v1'
        )
        none_described, none_total = artifacts.description_coverage(
            'application-v1'
        )
        empty_described, empty_total = artifacts.description_coverage(
            'sso-v1'
        )
        assert full_total and full_described == full_total
        assert partial_total and 0 < partial_described < partial_total
        assert none_total and none_described == 0
        assert empty_total == 0

        content = self.client.get('/api/docs/').content.decode()
        assert (
            f'Fully documented ({full_described}/{full_total} fields)'
            in content
        )
        assert (
            f'Partly documented ({partial_described}/{partial_total} '
            'fields)' in content
        )
        assert (
            'No field descriptions yet '
            f'({none_described}/{none_total} fields)' in content
        )
        assert 'No response fields declared' in content

    def test_index_links_the_machine_readable_bundle(self):
        content = self.client.get('/api/docs/').content.decode()
        assert '/api/openapi.json' in content


class TestDocsPage(TestCase):

    def setUp(self):
        self.client = Client()

    def test_serves_the_built_page(self):
        with patch(
            'corehq.apps.api.openapi.artifacts.read_page',
            return_value='<html>redoc</html>',
        ):
            response = self.client.get('/api/docs/user-v1/')
        assert response.status_code == 200
        assert response.content == b'<html>redoc</html>'

    def test_unknown_slug_is_404_without_reading_the_filesystem(self):
        with patch(
            'corehq.apps.api.openapi.artifacts.read_page'
        ) as read_page:
            response = self.client.get('/api/docs/not-a-real-api/')
        assert response.status_code == 404
        read_page.assert_not_called()

    def test_missing_artifact_names_the_build_command_in_debug(self):
        with patch(
            'corehq.apps.api.openapi.artifacts.read_page', return_value=None
        ):
            with self.settings(DEBUG=True):
                response = self.client.get('/api/docs/user-v1/')
        assert response.status_code == 404
        assert b'yarn openapi:docs' in response.content

    def test_missing_artifact_says_nothing_outside_debug(self):
        with patch(
            'corehq.apps.api.openapi.artifacts.read_page', return_value=None
        ):
            with self.settings(DEBUG=False):
                response = self.client.get('/api/docs/user-v1/')
        assert response.status_code == 404
        assert response.content == b''
