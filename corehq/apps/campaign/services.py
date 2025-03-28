from corehq.apps.es import CaseSearchES


def get_gauge_metric_value(gauge):
    return metric_function_mapping[gauge.metric](gauge)


def _get_number_of_cases(gauge):
    case_type = gauge.case_type
    domain = gauge.dashboard.domain
    return CaseSearchES().domain(domain).case_type(case_type).count()


metric_function_mapping = {
    'total_number_of_cases': _get_number_of_cases,
}
