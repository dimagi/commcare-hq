from unittest.mock import patch

from corehq.apps.case_search.utils import get_expanded_case_results
from corehq.form_processor.models import CommCareCaseSQL


@patch("corehq.apps.case_search.utils._get_case_search_cases")
def test_get_expanded_case_results(get_cases_mock):
    cases = [
        CommCareCaseSQL(case_json={}),
        CommCareCaseSQL(case_json={"potential_duplicate_id": "123"}),
        CommCareCaseSQL(case_json={"potential_duplicate_id": "456"}),
        CommCareCaseSQL(case_json={"potential_duplicate_id": ""}),
        CommCareCaseSQL(case_json={"potential_duplicate_id": None}),
    ]
    helper = None
    get_expanded_case_results(helper, "potential_duplicate_id", cases)
    get_cases_mock.assert_called_with(helper, {"123", "456"})
