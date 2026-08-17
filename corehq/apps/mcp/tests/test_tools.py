import pytest

from corehq.apps.fixtures.models import LookupTable
from corehq.apps.mcp.tools import ToolError, list_apis, list_lookup_tables, whoami
from corehq.apps.mcp.tests.utils import McpTestCase


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
