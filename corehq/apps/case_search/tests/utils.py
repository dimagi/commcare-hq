from corehq.apps.case_search.models import criteria_dict_to_criteria_list
from corehq.apps.case_search.utils import (
    CaseSearchQueryBuilder,
    QueryHelper,
)


def get_case_search_query(domain, case_types, criteria_dict, commcare_sort=None):
    """Helper function for tests"""
    criteria = criteria_dict_to_criteria_list(criteria_dict)
    builder = CaseSearchQueryBuilder(QueryHelper(domain), case_types)
    return builder.build_query(criteria, commcare_sort=commcare_sort)
