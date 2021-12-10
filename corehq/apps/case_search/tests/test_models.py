from unittest.mock import call, patch

from django.test import TestCase

from testil import assert_raises, eq

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.models import (
    CASE_SEARCH_REGISTRY_ID_KEY,
    CaseSearchRequestConfig,
    disable_case_search,
    enable_case_search,
    extract_search_request_config,
)
from corehq.util.test_utils import generate_cases


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


@generate_cases([
    (None, False),
    ("reg1", False),
    (["reg1"], True),  # disallow list
])
def test_extract_criteria_config(self, commcare_registry, expect_exception):
    with assert_raises(None if not expect_exception else CaseSearchUserError):
        config = extract_search_request_config({
            CASE_SEARCH_REGISTRY_ID_KEY: commcare_registry,
            "other_key": "jim",
            "case_type": "bob"
        })
        eq(config, CaseSearchRequestConfig(commcare_registry=commcare_registry))
