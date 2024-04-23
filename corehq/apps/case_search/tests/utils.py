from corehq.apps.case_search.models import criteria_dict_to_criteria_list
from corehq.apps.case_search.utils import (
    CaseSearchProfiler,
    CaseSearchQueryBuilder,
)


def get_case_search_query(domain, case_types, criteria_dict, commcare_sort=None):
    """Helper function for tests"""
    criteria = criteria_dict_to_criteria_list(criteria_dict)
    builder = CaseSearchQueryBuilder(domain, case_types, CaseSearchProfiler())
    return builder.build_query(criteria, commcare_sort=commcare_sort)
