from testil import assert_raises, eq

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.filter_dsl import CaseFilterError
from corehq.apps.case_search.models import (
    CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY,
    CASE_SEARCH_CASE_TYPE_KEY,
    CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY,
    CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY,
    CASE_SEARCH_MODULE_NAME_TAG_KEY,
    CASE_SEARCH_REGISTRY_ID_KEY,
    CASE_SEARCH_SORT_KEY,
    CaseSearchRequestConfig,
    SearchCriteria,
    extract_search_request_config,
)
from corehq.util.test_utils import generate_cases


@generate_cases([
    ("jelly", None, None, True, None, False),
    (["jelly", "tots"], None, None, True, None, False),
    (None, None, None, True, None, True),  # required case type
    ("jelly", "reg1", "dupe_id", False, None, False),
    ("jelly", None, None, False, ["name,-date_of_birth:date"], False),
    # disallow lists
    ("jelly", None, ["dupe_id1", "dupe_id2"], False, None, True),
    ("jelly", ["reg1", "reg2"], None, False, None, True),
])
def test_extract_criteria_config(self, case_type, data_registry, custom_related_case_property,
                            include_all_related_cases, commcare_sort, expect_exception):
    with assert_raises(None if not expect_exception else CaseSearchUserError):
        request_dict = _make_request_dict({
            CASE_SEARCH_CASE_TYPE_KEY: case_type,
            CASE_SEARCH_REGISTRY_ID_KEY: data_registry,
            CASE_SEARCH_CUSTOM_RELATED_CASE_PROPERTY_KEY: custom_related_case_property,
            CASE_SEARCH_INCLUDE_ALL_RELATED_CASES_KEY: include_all_related_cases,
            CASE_SEARCH_SORT_KEY: commcare_sort,
            CASE_SEARCH_MODULE_NAME_TAG_KEY: "module_name",
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
            commcare_sort=commcare_sort,
        ))


def _make_request_dict(params):
    """All values must be a list to match what we get from Django during a request.
    """
    return {
        key: (value if isinstance(value, list) else [value])
        for key, value in params.items() if value is not None
    }


@generate_cases([
    (CASE_SEARCH_BLACKLISTED_OWNER_ID_KEY, ["a", "b"]),
    ("owner_id", ["a", "b"]),
    ("date", ["a", "__range__2022-01-01__2022-02-01"]),
    ("date", "__range__2022-01-01__2022"),
])
def test_search_criteria_validate(self, key, value):
    with assert_raises(CaseFilterError):
        SearchCriteria(key, value).validate()
