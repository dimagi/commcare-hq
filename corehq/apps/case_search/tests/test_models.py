from unittest.mock import call, patch

from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from testil import assert_raises, eq

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.models import (
    CASE_SEARCH_EXPAND_ID_PROPERTY_KEY,
    CASE_SEARCH_REGISTRY_ID_KEY,
    CaseSearchRequestConfig,
    disable_case_search,
    enable_case_search,
    extract_search_request_config,
    CASE_SEARCH_CASE_TYPE_KEY,
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
    ("jelly", None, None, False),
    (["jelly", "tots"], None, None, False),
    (None, None, None, True),  # required case type
    ("jelly", "reg1", "dupe_id", False),
    # disallow lists
    ("jelly", None, ["dupe_id1", "dupe_id2"], True),
    ("jelly", ["reg1", "reg2"], None, True),
])
def test_extract_criteria_config(self, case_type, data_registry, expand_id_property, expect_exception):
    with assert_raises(None if not expect_exception else CaseSearchUserError):
        request_dict = _make_request_dict({
            CASE_SEARCH_CASE_TYPE_KEY: case_type,
            CASE_SEARCH_REGISTRY_ID_KEY: data_registry,
            CASE_SEARCH_EXPAND_ID_PROPERTY_KEY: expand_id_property,
            "other_key": "jim",
        })
        config = extract_search_request_config(request_dict)

    if not expect_exception:
        eq(config, CaseSearchRequestConfig(
            criteria={"other_key": "jim"},
            case_type=case_type, data_registry=data_registry, expand_id_property=expand_id_property
        ))


def test_extract_criteria_config_legacy():
    config = extract_search_request_config(_make_request_dict({
        CASE_SEARCH_CASE_TYPE_KEY: "type",
        "commcare_registry": "reg1",
    }))
    eq(config, CaseSearchRequestConfig(criteria={}, case_type="type", data_registry="reg1"))


def _make_request_dict(params):
    """All values must be a list to match what we get from Django during a request.
    """
    request_dict = MultiValueDict()
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, list):
            request_dict.setlist(key, value)
        else:
            request_dict[key] = value
    return request_dict
