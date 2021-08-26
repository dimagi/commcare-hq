from casexml.apps.case.models import CommCareCase

from corehq.apps.es import queries
from corehq.apps.es.case_search import CaseSearchES, flatten_result

DUPLICATE_LIMIT = 1000


def find_duplicate_cases(domain, case, case_properties, include_closed=False, match_type="ALL"):
    es = CaseSearchES().domain(domain).size(DUPLICATE_LIMIT).case_type(case.type)

    if not include_closed:
        es = es.is_closed(False)

    clause = queries.MUST if match_type == "ALL" else queries.SHOULD

    for case_property_name in case_properties:
        es = es.case_property_query(
            case_property_name,
            case.get_case_property(case_property_name) or '',
            clause
        )
    return [CommCareCase.wrap(flatten_result(hit)) for hit in es.run().hits]
