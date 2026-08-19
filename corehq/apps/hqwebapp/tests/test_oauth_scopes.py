from unittest.mock import Mock

from django.test import SimpleTestCase

from oauth2_provider.scopes import get_scopes_backend

from corehq.apps.hqwebapp.oauth_scopes import HQScopes


class TestHQScopesBackend(SimpleTestCase):

    def test_is_the_configured_scopes_backend(self):
        assert isinstance(get_scopes_backend(), HQScopes)

    def test_describes_static_and_domain_scopes(self):
        all_scopes = HQScopes().get_all_scopes()
        assert 'Access API' in all_scopes['access_apis']
        assert 'new-project' in all_scopes['domain:new-project']

    def test_available_scopes_include_requested_domain_scopes(self):
        request = Mock(scopes=['access_apis', 'domain:my-project'])
        available = HQScopes().get_available_scopes(request=request)
        assert 'access_apis' in available
        assert 'domain:my-project' in available
        assert 'domain:other' not in available

    def test_default_scopes_have_no_domain_restriction(self):
        assert not any(
            scope.startswith('domain:')
            for scope in HQScopes().get_default_scopes()
        )
