from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES_MAP
from corehq.apps.es import queries
from corehq.apps.es.case_search import CaseSearchES

DUPLICATE_LIMIT = 1000


def find_duplicate_case_ids(domain, case, case_properties, include_closed=False, match_type="ALL"):
    es = CaseSearchES().domain(domain).size(DUPLICATE_LIMIT).case_type(case.type)

    if not include_closed:
        es = es.is_closed(False)

    clause = queries.MUST if match_type == "ALL" else queries.SHOULD
    _case_json = None

    for case_property_name in case_properties:
        if case_property_name in SPECIAL_CASE_PROPERTIES_MAP:
            if _case_json is None:
                _case_json = case.to_json()
            case_property_value = SPECIAL_CASE_PROPERTIES_MAP[case_property_name].value_getter(_case_json)
        else:
            case_property_value = case.get_case_property(case_property_name)

        es = es.case_property_query(
            case_property_name,
            case_property_value or '',
            clause
        )
    return es.get_ids()
