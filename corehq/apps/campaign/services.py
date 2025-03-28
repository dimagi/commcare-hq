from corehq.apps.es import CaseSearchES


def get_gauge_metric_value(gauge):
    return metric_function_mapping[gauge.metric](gauge)


def _get_number_of_cases(gauge):
    case_type = gauge.case_type
    domain = gauge.dashboard.domain
    case_es_query = CaseSearchES().domain(domain)
    if case_type:
        case_es_query = case_es_query.case_type(case_type)
    return case_es_query.count()


metric_function_mapping = {
    'total_number_of_cases': _get_number_of_cases,
}
