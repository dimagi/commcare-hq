from corehq.apps.case_search.utils import CaseSearchQueryBuilder


def get_case_search_query(domain, case_types, criteria_dict):
    """Helper function for tests. In the future this will handle conversion
    of the criteria from a dict to a list of Criteria objects"""
    return CaseSearchQueryBuilder(domain, case_types, criteria_dict).search_es
