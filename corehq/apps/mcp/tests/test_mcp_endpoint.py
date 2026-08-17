from django.test import TestCase

from corehq.apps.mcp.tests.utils import McpTestCase


class TestMcpAuthentication(TestCase):

    def test_unauthenticated_request_gets_401_pointing_at_resource_metadata(self):
        response = self.client.post('/mcp', data='{}', content_type='application/json')
        assert response.status_code == 401
        assert response['WWW-Authenticate'] == (
            'Bearer resource_metadata='
            '"http://testserver/.well-known/oauth-protected-resource/mcp"'
        )


class TestMcpInitialize(McpTestCase):

    def test_initialize_returns_server_info_and_tool_capability(self):
        message = self.rpc('initialize', {
            'protocolVersion': '2025-06-18',
            'capabilities': {},
            'clientInfo': {'name': 'test-client', 'version': '0'},
        })
        assert message['id'] == 1
        result = message['result']
        assert result['protocolVersion'] == '2025-06-18'
        assert result['capabilities'] == {'tools': {}}
        assert result['serverInfo']['name'] == 'commcare-hq'

    def test_initialized_notification_returns_202(self):
        response = self.mcp_post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        assert response.status_code == 202


class TestMcpToolsList(McpTestCase):

    def test_tools_list_returns_registered_tools_with_schemas(self):
        result = self.rpc('tools/list')['result']
        tools = {tool['name']: tool for tool in result['tools']}
        assert set(tools) == {
            'whoami', 'list_lookup_tables', 'list_apis',
            'call_api_read', 'call_api_write'}
        for tool in tools.values():
            assert tool['description']
            assert tool['inputSchema']['type'] == 'object'
        assert tools['list_lookup_tables']['inputSchema']['required'] == ['domain']


class TestMcpToolsCall(McpTestCase):

    def test_call_whoami_returns_tool_result_content(self):
        import json
        result = self.rpc('tools/call', {'name': 'whoami', 'arguments': {}})['result']
        assert result['isError'] is False
        (block,) = result['content']
        assert block['type'] == 'text'
        payload = json.loads(block['text'])
        assert payload == {'username': 'mcp-user@example.com', 'domains': [self.domain]}

    def test_tool_error_is_reported_as_tool_result_not_crash(self):
        result = self.rpc('tools/call', {
            'name': 'list_lookup_tables',
            'arguments': {'domain': 'not-my-domain'},
        })['result']
        assert result['isError'] is True
        assert "not a member of domain 'not-my-domain'" in result['content'][0]['text']

    def test_superuser_token_does_not_grant_access_to_non_member_domains(self):
        # Regression guard: OAuth-authenticated superusers must not pass
        # is_member_of via is_global_admin (see _oauth2_check).
        self.user.is_superuser = True
        self.user.save()
        result = self.rpc('tools/call', {
            'name': 'list_lookup_tables',
            'arguments': {'domain': 'not-my-domain'},
        })['result']
        assert result['isError'] is True


class TestMcpProtocolErrors(McpTestCase):

    def test_token_without_required_scope_gets_401(self):
        from datetime import timedelta

        from django.utils import timezone
        from oauth2_provider.models import AccessToken
        AccessToken.objects.create(
            user=self.user.get_django_user(),
            token='wrong-scope-token',
            application=self.application,
            scope='sync',
            expires=timezone.now() + timedelta(hours=1),
        )
        response = self.mcp_post(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            token='wrong-scope-token',
        )
        assert response.status_code == 401

    def test_malformed_json_body_returns_parse_error(self):
        response = self.client.post(
            '/mcp', data='{not json', content_type='application/json',
            HTTP_AUTHORIZATION='Bearer test-mcp-access-token')
        assert response.status_code == 400
        assert response.json()['error']['code'] == -32700

    def test_unknown_method_returns_method_not_found(self):
        response = self.mcp_post({'jsonrpc': '2.0', 'id': 5, 'method': 'resources/list'})
        assert response.status_code == 200
        error = response.json()['error']
        assert error['code'] == -32601
        assert 'resources/list' in error['message']

    def test_unknown_tool_returns_invalid_params_error(self):
        response = self.mcp_post({
            'jsonrpc': '2.0', 'id': 6, 'method': 'tools/call',
            'params': {'name': 'launch_missiles', 'arguments': {}},
        })
        assert response.status_code == 200
        error = response.json()['error']
        assert error['code'] == -32602
        assert 'launch_missiles' in error['message']

    def test_get_request_is_not_allowed(self):
        response = self.client.get(
            '/mcp', HTTP_AUTHORIZATION='Bearer test-mcp-access-token')
        assert response.status_code == 405


class TestDomainScopedTokenOnEndpoint(McpTestCase):

    def test_domain_scoped_token_cannot_call_tools_in_other_domains(self):
        from datetime import timedelta

        from django.utils import timezone
        from oauth2_provider.models import AccessToken
        AccessToken.objects.create(
            user=self.user.get_django_user(),
            token='domain-scoped-token',
            application=self.application,
            scope='access_apis domain:some-other-domain',
            expires=timezone.now() + timedelta(hours=1),
        )
        response = self.mcp_post({
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'list_lookup_tables',
                       'arguments': {'domain': self.domain}},
        }, token='domain-scoped-token')
        result = response.json()['result']
        assert result['isError'] is True
        assert 'not scoped' in result['content'][0]['text']
