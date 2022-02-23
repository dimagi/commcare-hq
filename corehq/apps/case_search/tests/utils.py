from corehq.apps.case_search.utils import CaseSearchCriteria


def get_case_search_query(domain, case_types, criteria_dict):
    """Helper function for tests. In the future this will handle conversion
    of the criteria from a dict to a list of Criteria objects"""
    return CaseSearchCriteria(domain, case_types, criteria_dict).search_es
