from django.test import TestCase


class TestProtectedResourceMetadata(TestCase):

    def test_rfc9728_document_describes_mcp_resource(self):
        response = self.client.get('/.well-known/oauth-protected-resource/mcp')
        assert response.status_code == 200
        doc = response.json()
        assert doc['resource'] == 'http://testserver/mcp'
        assert doc['authorization_servers'] == ['http://testserver']
        assert doc['bearer_methods_supported'] == ['header']
        assert doc['scopes_supported'] == ['access_apis']
