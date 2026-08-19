"""The OAuth consent screen lets the user restrict a grant to one of
their project spaces; the granted authorization then carries a
``domain:<name>`` scope that the token inherits.
"""
import re

from oauth2_provider.models import Grant, get_application_model

from corehq.apps.mcp.tests.utils import McpTestCase

AUTHORIZE = '/oauth/authorize/'


class TestDomainChoiceOnConsentScreen(McpTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.oauth_client = get_application_model().objects.create(
            name='authorize-test-client',
            client_type='confidential',
            authorization_grant_type='authorization-code',
            redirect_uris='http://testserver/callback',
        )

    def setUp(self):
        super().setUp()
        assert self.client.login(
            username='mcp-user@example.com', password='secret')

    def _authorize_params(self):
        return {
            'client_id': self.oauth_client.client_id,
            'response_type': 'code',
            'redirect_uri': 'http://testserver/callback',
            'scope': 'access_apis',
            'state': 'teststate',
        }

    def _post_consent(self, domain):
        params = self._authorize_params()
        return self.client.post(AUTHORIZE, data={
            **params,
            'domain': domain,
            'allow': 'Authorize',
        })

    def _granted_scope(self):
        return Grant.objects.get(application=self.oauth_client).scope

    def test_consent_screen_offers_the_users_domains(self):
        response = self.client.get(AUTHORIZE, self._authorize_params())
        assert response.status_code == 200
        content = response.content.decode()
        assert 'All my project spaces' in content
        assert 'mcp-test-domain' in content

    def test_choosing_a_domain_adds_a_domain_scope_to_the_grant(self):
        response = self._post_consent('mcp-test-domain')
        assert response.status_code == 302
        assert 'code=' in response['Location']
        assert self._granted_scope() == 'access_apis domain:mcp-test-domain'

    def test_choosing_all_project_spaces_grants_no_domain_scope(self):
        response = self._post_consent('')
        assert response.status_code == 302
        assert self._granted_scope() == 'access_apis'

    def test_cannot_grant_a_domain_the_user_is_not_a_member_of(self):
        response = self._post_consent('someone-elses-domain')
        assert not Grant.objects.filter(application=self.oauth_client).exists()
        assert response.status_code != 302


class TestRequestedDomainScopePreselection(TestDomainChoiceOnConsentScreen):

    def _get_consent_screen(self, scope):
        params = {**self._authorize_params(), 'scope': scope}
        return self.client.get(AUTHORIZE, params).content.decode()

    def test_requested_member_domain_is_preselected(self):
        content = self._get_consent_screen('access_apis domain:mcp-test-domain')
        assert re.search(
            r'<option value="mcp-test-domain"[^>]* selected', content)

    def test_requested_non_member_domain_is_not_preselected(self):
        content = self._get_consent_screen('access_apis domain:not-mine')
        assert not re.search(r'<option value="[^"]+"[^>]* selected', content)

    def test_picker_choice_overrides_requested_domain_scope(self):
        params = self._authorize_params()
        response = self.client.post(AUTHORIZE, data={
            **params,
            'scope': 'access_apis domain:mcp-test-domain',
            'domain': '',  # user chose "All my project spaces"
            'allow': 'Authorize',
        })
        assert response.status_code == 302
        assert self._granted_scope() == 'access_apis'

    def test_requested_and_picked_domain_do_not_duplicate(self):
        params = self._authorize_params()
        response = self.client.post(AUTHORIZE, data={
            **params,
            'scope': 'access_apis domain:mcp-test-domain',
            'domain': 'mcp-test-domain',
            'allow': 'Authorize',
        })
        assert response.status_code == 302
        assert self._granted_scope() == 'access_apis domain:mcp-test-domain'
