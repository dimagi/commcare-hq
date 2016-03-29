import mock
from django.test import SimpleTestCase

from corehq.apps.case_search.api import enable_case_search


class TestCaseSearch(SimpleTestCase):
    domain = "meereen"

    @mock.patch('corehq.apps.case_search.tasks.get_couch_case_search_reindexer')
    def test_enable_case_search_reindex(self, fake_reindexer):
        """
        When case search is enabled, reindex that domains cases
        """
        enable_case_search(self.domain)
        self.assertTrue(fake_reindexer.called_with(self.domain))
        self.assertTrue(fake_reindexer().reindex.called)
