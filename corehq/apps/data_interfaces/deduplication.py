from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es import queries

DUPLICATE_LIMIT = 1000


def find_duplicate_ids_for_case(domain, case, case_properties, include_closed=False, match_type="ALL"):
    es = CaseSearchES().domain(domain).size(DUPLICATE_LIMIT)

    if not include_closed:
        es = es.is_closed(False)

    clause = queries.MUST if match_type == "ALL" else queries.SHOULD

    for case_property_name in case_properties:
        es = es.case_property_query(
            case_property_name,
            case.get_case_property(case_property_name) or '',
            clause
        )

    return es.get_ids()
