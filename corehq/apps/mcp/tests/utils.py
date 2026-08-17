import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from oauth2_provider.models import AccessToken, get_application_model

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.mcp.tools import ToolContext
from corehq.apps.users.models import WebUser


class McpTestCase(TestCase):
    """Base class providing a web user with a real OAuth access token."""
    domain = 'mcp-test-domain'

    @classmethod
    def setUpTestData(cls):
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(cls.domain, 'mcp-user@example.com', 'secret', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)
        cls.application = get_application_model().objects.create(
            name='test-mcp-client',
            client_type='confidential',
            authorization_grant_type='authorization-code',
        )
        cls.access_token = AccessToken.objects.create(
            user=cls.user.get_django_user(),
            token='test-mcp-access-token',
            application=cls.application,
            scope='access_apis',
            expires=timezone.now() + timedelta(hours=1),
        )

    @property
    def context(self):
        return ToolContext(
            couch_user=self.user,
            authorization='Bearer test-mcp-access-token',
        )

    def mcp_post(self, body, token='test-mcp-access-token'):
        return self.client.post(
            '/mcp',
            data=json.dumps(body),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

    def rpc(self, method, params=None, req_id=1):
        response = self.mcp_post(
            {'jsonrpc': '2.0', 'id': req_id, 'method': method, 'params': params or {}})
        assert response.status_code == 200, response.content
        return response.json()
