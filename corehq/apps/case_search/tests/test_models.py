from corehq.apps.case_search.models import disable_case_search, enable_case_search
from django.test import TestCase
from mock import call, patch


class TestCaseSearch(TestCase):
    domain = "meereen"

    @patch('corehq.apps.case_search.tasks.get_case_search_reindexer')
    def test_enable_case_search_reindex(self, fake_reindexer):
        """
        When case search is enabled, reindex that domains cases
        """
        enable_case_search(self.domain)
        self.assertEqual(fake_reindexer.call_args, call(self.domain))
        self.assertTrue(fake_reindexer().reindex.called)

    @patch('corehq.apps.case_search.tasks.delete_case_search_cases')
    def test_disable_case_search_reindex(self, fake_deleter):
        """
        When case search is disabled, delete that domains cases
        """
        with patch('corehq.apps.case_search.tasks.get_case_search_reindexer'):
            enable_case_search(self.domain)

        disable_case_search(self.domain)
        self.assertEqual(fake_deleter.call_args, call(self.domain))
