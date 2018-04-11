from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.case_search.models import disable_case_search, enable_case_search
from django.test import TestCase
from mock import call, patch


class TestCaseSearch(TestCase):
    domain = "meereen"

    @patch('corehq.apps.case_search.tasks.CaseSearchReindexerFactory')
    def test_enable_case_search_reindex(self, fake_factor):
        """
        When case search is enabled, reindex that domains cases
        """
        enable_case_search(self.domain)
        self.assertEqual(fake_factor.call_args, call(domain=self.domain))
        self.assertTrue(fake_factor().build.called)
        self.assertTrue(fake_factor().build().reindex.called)

    @patch('corehq.apps.case_search.tasks.delete_case_search_cases')
    def test_disable_case_search_reindex(self, fake_deleter):
        """
        When case search is disabled, delete that domains cases
        """
        with patch('corehq.apps.case_search.tasks.CaseSearchReindexerFactory'):
            enable_case_search(self.domain)

        disable_case_search(self.domain)
        self.assertEqual(fake_deleter.call_args, call(self.domain))
