from django.test import TestCase


class TestOAuthAuthorizationServerMetadata(TestCase):

    def test_rfc8414_document_describes_hq_oauth_provider(self):
        response = self.client.get('/.well-known/oauth-authorization-server')
        assert response.status_code == 200
        doc = response.json()
        assert doc['issuer'] == 'http://testserver'
        assert doc['authorization_endpoint'] == 'http://testserver/oauth/authorize/'
        assert doc['token_endpoint'] == 'http://testserver/oauth/token/'
        assert doc['revocation_endpoint'] == 'http://testserver/oauth/revoke_token/'
        assert doc['introspection_endpoint'] == 'http://testserver/oauth/introspect/'
        assert doc['response_types_supported'] == ['code']
        assert doc['grant_types_supported'] == ['authorization_code', 'refresh_token']
        assert doc['code_challenge_methods_supported'] == ['S256']
        assert 'access_apis' in doc['scopes_supported']
