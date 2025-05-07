from unittest.mock import patch

from corehq.apps.case_search.utils import (
    CaseSearchProfiler,
    get_expanded_case_results,
)
from corehq.apps.es import CaseSearchES
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


def test_profiler_search_class():
    profiler = CaseSearchProfiler()
    assert profiler.search_class == CaseSearchES
