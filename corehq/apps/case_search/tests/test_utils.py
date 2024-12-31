from unittest.mock import patch

import pytest

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.case_search.utils import (
    CaseSearchQueryBuilder,
    QueryHelper,
    get_expanded_case_results,
)
from corehq.form_processor.models import CommCareCase


@patch("corehq.apps.case_search.utils._get_case_search_cases")
def test_get_expanded_case_results(get_cases_mock):
    cases = [
        CommCareCase(case_json={}),
        CommCareCase(case_json={"potential_duplicate_id": "123"}),
        CommCareCase(case_json={"potential_duplicate_id": "456"}),
        CommCareCase(case_json={"potential_duplicate_id": ""}),
        CommCareCase(case_json={"potential_duplicate_id": None}),
    ]
    helper = None
    get_expanded_case_results(helper, "potential_duplicate_id", cases)
    get_cases_mock.assert_called_with(helper, {"123", "456"})


@pytest.mark.parametrize("xpath_vars, xpath_query, result", [
    ({'name': 'Ethan'}, "name = '{name}'", "name = 'Ethan'"),
    ({'ssn_matches': 'social_security_number = "123abc"'},
     '{ssn_matches} or subcase-exists("parent", @case_type = "alias" and {ssn_matches})',
     'social_security_number = "123abc" or subcase-exists('
     '"parent", @case_type = "alias" and social_security_number = "123abc")'),
    ({'ssn_matches': 'social_security_number = "123abc"'}, 'match-all()', 'match-all()'),
])
def test_xpath_vars(xpath_vars, xpath_query, result):
    helper = QueryHelper('mydomain')
    helper.config = CaseSearchConfig(domain='mydomain')
    builder = CaseSearchQueryBuilder(helper, ['mycasetype'], xpath_vars)
    with patch("corehq.apps.case_search.utils.build_filter_from_xpath") as build:
        builder._build_filter_from_xpath(xpath_query)
        assert build.call_args.args[0] == result


def test_xpath_vars_misconfigured():
    xpath_vars = {}  # No variables defined!
    xpath_query = "name = '{name}'"  # 'name' is not specified
    helper = QueryHelper('mydomain')
    helper.config = CaseSearchConfig(domain='mydomain')
    builder = CaseSearchQueryBuilder(helper, ['mycasetype'], xpath_vars)
    with pytest.raises(CaseSearchUserError) as e_info:
        builder._build_filter_from_xpath(xpath_query)
    e_info.match("Variable 'name' not found")
