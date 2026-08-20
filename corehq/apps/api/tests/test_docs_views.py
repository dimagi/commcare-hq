import json
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase

from corehq.apps.api.docs_views import SPEC_CACHE_SECONDS, with_host
from corehq.apps.api.openapi import artifacts, response_fields


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

    def test_view_documented_spec_is_served(self):
        # case-v2 is documented on function-based views (not the catalogue),
        # so its spec is generated and committed but reachable only if the
        # served-slug allowlist knows about the view docs too.
        response = self.client.get('/api/docs/case-v2/openapi.json')
        assert response.status_code == 200
        document = json.loads(response.content)
        assert '/a/{domain}/api/case/v2/' in document['paths']

    def test_missing_spec_names_the_regenerate_command_in_debug(self):
        # The slug is in the allowlist but the file is absent -- a checkout
        # that has not run ./manage.py generate_openapi. Distinct from an
        # unknown slug, and the only branch of api_spec() with no coverage.
        with patch(
            'corehq.apps.api.openapi.artifacts.read_spec', return_value=None
        ):
            with self.settings(DEBUG=True):
                response = self.client.get('/api/docs/user-v1/openapi.json')
        assert response.status_code == 404
        assert b'generate_openapi' in response.content

    def test_missing_spec_says_nothing_outside_debug(self):
        with patch(
            'corehq.apps.api.openapi.artifacts.read_spec', return_value=None
        ):
            response = self.client.get('/api/docs/user-v1/openapi.json')
        assert response.status_code == 404
        assert response.content == b''

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


class TestSpecCaching(TestCase):
    """The specs replace public reference pages, so repeat visits should not
    re-transfer them. ``bundle.json`` is over 400 KB, and by default
    ``NoCacheMiddleware`` marks every response ``no-store``."""

    def setUp(self):
        self.client = Client()

    def test_a_spec_is_cacheable_rather_than_no_store(self):
        response = self.client.get('/api/openapi.json')
        assert response['Cache-Control'] == f'max-age={SPEC_CACHE_SECONDS}'
        assert 'no-store' not in response['Cache-Control']

    def test_the_content_type_survives_the_middlewares_rewrite(self):
        """``NoCacheMiddleware`` rewrites Content-Type from the URL's
        extension for any response that opts into caching. Every spec route
        ends in ``.json``, which is the only reason that is harmless."""
        for url in (
            '/api/openapi.json',
            '/api/docs/user-v1/openapi.json',
            '/.well-known/openapi.json',
        ):
            response = self.client.get(url)
            assert response['Content-Type'] == 'application/json', url

    def test_a_matching_if_none_match_gets_a_bodiless_304(self):
        first = self.client.get('/api/openapi.json')
        assert first.status_code == 200
        assert len(first.content) > 100_000

        again = self.client.get(
            '/api/openapi.json', HTTP_IF_NONE_MATCH=first['ETag']
        )
        assert again.status_code == 304
        assert again.content == b''
        assert again['ETag'] == first['ETag']

    def test_a_304_still_carries_the_caching_headers(self):
        """Otherwise the client is told to discard the copy it just
        offered, and the next visit re-transfers the whole document."""
        first = self.client.get('/api/openapi.json')
        again = self.client.get(
            '/api/openapi.json', HTTP_IF_NONE_MATCH=first['ETag']
        )
        assert again['Cache-Control'] == f'max-age={SPEC_CACHE_SECONDS}'

    def test_a_stale_if_none_match_gets_the_full_document(self):
        response = self.client.get(
            '/api/openapi.json', HTTP_IF_NONE_MATCH='"not-the-current-etag"'
        )
        assert response.status_code == 200
        assert json.loads(response.content)['openapi'] == '3.0.3'

    def test_a_wildcard_if_none_match_matches(self):
        response = self.client.get('/api/openapi.json', HTTP_IF_NONE_MATCH='*')
        assert response.status_code == 304

    def test_a_weak_etag_is_compared_weakly(self):
        """If-None-Match uses weak comparison; a proxy may relay a tag back
        with a ``W/`` prefix that this view never emitted."""
        first = self.client.get('/api/openapi.json')
        again = self.client.get(
            '/api/openapi.json', HTTP_IF_NONE_MATCH=f'W/{first["ETag"]}'
        )
        assert again.status_code == 304

    def test_one_of_several_offered_etags_matches(self):
        first = self.client.get('/api/openapi.json')
        again = self.client.get(
            '/api/openapi.json',
            HTTP_IF_NONE_MATCH=f'"stale-one", {first["ETag"]}, "stale-two"',
        )
        assert again.status_code == 304

    def test_another_hosts_etag_does_not_match(self):
        """The ETag keys on host as well as content, so a cache cannot
        serve one deployment's document as another's."""
        first = self.client.get(
            '/api/openapi.json', HTTP_HOST='a.example.org'
        )
        other = self.client.get(
            '/api/openapi.json',
            HTTP_HOST='b.example.org',
            HTTP_IF_NONE_MATCH=first['ETag'],
        )
        assert other.status_code == 200
        document = json.loads(other.content)
        host = document['servers'][0]['variables']['host']['default']
        assert host == 'b.example.org'

    def test_the_html_index_is_left_uncached(self):
        """Its URL has no extension, so the middleware's caching branch
        would rewrite Content-Type to None. Deliberately not opted in.

        The index is asserted rather than a reference page because it needs
        no build step: a Redoc page 404s unless ``yarn openapi:docs`` has
        run, which would make this pass without checking anything."""
        response = self.client.get('/api/docs/')
        assert response.status_code == 200
        assert response['Content-Type'].startswith('text/html')
        assert 'no-store' in response['Cache-Control']


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
        full_described, full_total = response_fields.description_coverage(
            artifacts.read_spec('user-v1')
        )
        partial_described, partial_total = response_fields.description_coverage(
            artifacts.read_spec('web-user-v1')
        )
        none_described, none_total = response_fields.description_coverage(
            artifacts.read_spec('user-domains-v1')
        )
        empty_described, empty_total = response_fields.description_coverage(
            artifacts.read_spec('sso-v1')
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
