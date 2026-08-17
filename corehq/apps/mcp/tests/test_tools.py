import pytest

from corehq.apps.fixtures.models import LookupTable
from corehq.apps.mcp.tools import ToolError, list_lookup_tables, whoami
from corehq.apps.mcp.tests.utils import McpTestCase


class TestWhoami(McpTestCase):

    def test_returns_username_and_domains(self):
        result = whoami(self.user, {})
        assert result == {
            'username': 'mcp-user@example.com',
            'domains': [self.domain],
        }


class TestListLookupTables(McpTestCase):

    def test_lists_tables_in_a_member_domain(self):
        table = LookupTable.objects.create(domain=self.domain, tag='villages')
        self.addCleanup(table.delete)
        result = list_lookup_tables(self.user, {'domain': self.domain})
        assert result == {
            'domain': self.domain,
            'lookup_tables': [
                {'id': str(table.id), 'tag': 'villages', 'is_global': False},
            ],
        }

    def test_rejects_domain_the_user_is_not_a_member_of(self):
        with pytest.raises(ToolError) as excinfo:
            list_lookup_tables(self.user, {'domain': 'not-my-domain'})
        assert "not a member of domain 'not-my-domain'" in str(excinfo.value)
