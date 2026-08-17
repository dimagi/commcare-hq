import pytest

from corehq.apps.fixtures.models import LookupTable
from corehq.apps.mcp.tools import (
    ToolError,
    call_api_read,
    call_api_write,
    list_apis,
    list_lookup_tables,
    whoami,
)
from corehq.apps.mcp.tests.utils import McpTestCase
from corehq.util.test_utils import flag_enabled


class TestWhoami(McpTestCase):

    def test_returns_username_and_domains(self):
        result = whoami(self.context, {})
        assert result == {
            'username': 'mcp-user@example.com',
            'domains': [self.domain],
        }


class TestListLookupTables(McpTestCase):

    def test_lists_tables_in_a_member_domain(self):
        table = LookupTable.objects.create(domain=self.domain, tag='villages')
        self.addCleanup(table.delete)
        result = list_lookup_tables(self.context, {'domain': self.domain})
        assert result == {
            'domain': self.domain,
            'lookup_tables': [
                {'id': str(table.id), 'tag': 'villages', 'is_global': False},
            ],
        }

    def test_rejects_domain_the_user_is_not_a_member_of(self):
        with pytest.raises(ToolError) as excinfo:
            list_lookup_tables(self.context, {'domain': 'not-my-domain'})
        assert "not a member of domain 'not-my-domain'" in str(excinfo.value)


class TestListApis(McpTestCase):

    def test_returns_api_catalog_with_paths_and_methods(self):
        result = list_apis(self.context, {})
        apis = {api['name']: api for api in result['apis']}
        lookup_table = apis['lookup_table']
        assert lookup_table['path'] == '/a/{domain}/api/v0.5/lookup_table/'
        assert lookup_table['list_methods'] == ['get', 'post']
        assert lookup_table['detail_methods'] == ['get', 'put', 'delete']
        assert 'web-user' in apis
        assert 'case' in apis


@flag_enabled('API_THROTTLE_WHITELIST')
class TestCallApiRead(McpTestCase):

    def test_reads_a_domain_api_with_the_callers_token(self):
        table = LookupTable.objects.create(domain=self.domain, tag='villages')
        self.addCleanup(table.delete)
        result = call_api_read(self.context, {
            'domain': self.domain,
            'path': 'v0.5/lookup_table/',
        })
        assert result['status'] == 200
        tags = [obj['tag'] for obj in result['body']['objects']]
        assert tags == ['villages']


@flag_enabled('API_THROTTLE_WHITELIST')
class TestCallApiWrite(McpTestCase):

    def test_creates_a_lookup_table_via_post(self):
        result = call_api_write(self.context, {
            'domain': self.domain,
            'path': 'v0.5/lookup_table/',
            'method': 'POST',
            'body': {
                'tag': 'clinics',
                'fields': [{'field_name': 'name', 'properties': []}],
                'item_attributes': [],
            },
        })
        assert result['status'] == 201, result
        table = LookupTable.objects.by_domain_tag(self.domain, 'clinics')
        self.addCleanup(table.delete)
        assert [f.field_name for f in table.fields] == ['name']

    def test_rejects_methods_that_are_not_writes(self):
        with pytest.raises(ToolError):
            call_api_write(self.context, {
                'domain': self.domain,
                'path': 'v0.5/lookup_table/',
                'method': 'TRACE',
                'body': {},
            })


@flag_enabled('API_THROTTLE_WHITELIST')
class TestApiBridgeGuardrails(McpTestCase):

    def test_rejects_paths_that_escape_the_domain_api_prefix(self):
        for path in ['../../hq/admin/', 'v0.5/../../admin/', 'v0.5/x/?q=1']:
            with pytest.raises(ToolError, match='Invalid API path'):
                call_api_read(self.context, {'domain': self.domain, 'path': path})

    def test_unknown_api_path_mentions_list_apis(self):
        with pytest.raises(ToolError, match='list_apis'):
            call_api_read(self.context, {'domain': self.domain, 'path': 'v9.9/nope/'})

    def test_api_permission_denial_passes_through_as_status(self):
        from datetime import timedelta

        from django.utils import timezone
        from oauth2_provider.models import AccessToken

        from corehq.apps.mcp.tools import ToolContext
        from corehq.apps.users.models import WebUser
        limited_user = WebUser.create(
            self.domain, 'limited@example.com', 'secret', None, None)
        self.addCleanup(limited_user.delete, self.domain, deleted_by=None)
        AccessToken.objects.create(
            user=limited_user.get_django_user(),
            token='limited-user-token',
            application=self.application,
            scope='access_apis',
            expires=timezone.now() + timedelta(hours=1),
        )
        context = ToolContext(
            couch_user=limited_user,
            authorization='Bearer limited-user-token',
        )
        result = call_api_read(context, {
            'domain': self.domain, 'path': 'v0.5/lookup_table/'})
        assert result['status'] in (401, 403), result
