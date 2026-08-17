"""Domain-scoped OAuth tokens: a token carrying ``domain:<name>`` scopes
may only act in those domains; tokens without domain scopes keep the
user's full access (grandfathering every token issued before this
feature existed).
"""
from datetime import timedelta

from django.utils import timezone

from oauth2_provider.models import AccessToken

from corehq.apps.mcp.tests.utils import McpTestCase
from corehq.util.test_utils import flag_enabled

API_PATH = '/a/mcp-test-domain/api/v0.5/lookup_table/'


@flag_enabled('API_THROTTLE_WHITELIST')
class TestDomainScopedTokenOnApis(McpTestCase):

    def _get_with_token_scope(self, scope):
        token = AccessToken.objects.create(
            user=self.user.get_django_user(),
            token=f'token-{scope.replace(" ", "-").replace(":", "_")}',
            application=self.application,
            scope=scope,
            expires=timezone.now() + timedelta(hours=1),
        )
        return self.client.get(
            API_PATH, HTTP_AUTHORIZATION=f'Bearer {token.token}')

    def test_token_without_domain_scope_is_unrestricted(self):
        response = self._get_with_token_scope('access_apis')
        assert response.status_code == 200

    def test_token_scoped_to_this_domain_is_allowed(self):
        response = self._get_with_token_scope('access_apis domain:mcp-test-domain')
        assert response.status_code == 200

    def test_token_scoped_to_another_domain_is_forbidden(self):
        response = self._get_with_token_scope('access_apis domain:some-other-domain')
        assert response.status_code == 403
