from unittest.mock import call, patch

from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from testil import assert_raises, eq

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.filter_dsl import CaseFilterError
from corehq.apps.case_search.models import (
    CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY,
    CASE_SEARCH_REGISTRY_ID_KEY,
    CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY,
    CaseSearchRequestConfig,
    disable_case_search,
    enable_case_search,
    extract_search_request_config,
    CASE_SEARCH_CASE_TYPE_KEY, SearchCriteria, CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY, CASE_SEARCH_XPATH_QUERY_KEY,
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
    ("jelly", None, None, True, False),
    (["jelly", "tots"], None, None, True, False),
    (None, None, None, True, True),  # required case type
    ("jelly", "reg1", "dupe_id", False, False),
    # disallow lists
    ("jelly", None, ["dupe_id1", "dupe_id2"], False, True),
    ("jelly", ["reg1", "reg2"], None, False, True),
])
def test_extract_criteria_config(self, case_type, data_registry, custom_related_case_property,
                            include_all_related_cases, expect_exception):
    with assert_raises(None if not expect_exception else CaseSearchUserError):
        request_dict = _make_request_dict({
            CASE_SEARCH_CASE_TYPE_KEY: case_type,
            CASE_SEARCH_REGISTRY_ID_KEY: data_registry,
            CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY: custom_related_case_property,
            CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY: include_all_related_cases,
            "other_key": "jim",
        })
        config = extract_search_request_config(request_dict)

    if not expect_exception:
        expected_case_types = case_type if isinstance(case_type, list) else [case_type]
        eq(config, CaseSearchRequestConfig(
            criteria=[SearchCriteria("other_key", "jim")],
            case_types=expected_case_types, data_registry=data_registry,
            custom_related_case_property=custom_related_case_property,
            include_all_related_cases=include_all_related_cases,
        ))


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


@generate_cases([
    (CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY, ["a", "b"]),
    ("owner_id", ["a", "b"]),
    ("date", ["a", "__range__2022-01-01__2022-02-01"]),
    ("date", "__range__2022-01-01__2022"),
])
def test_search_criteria_validate(self, key, value):
    with assert_raises(CaseFilterError):
        SearchCriteria(key, value).validate()
