from corehq.apps.es import CaseSearchES, FormES, UserES


def get_gauge_metric_value(gauge):
    if gauge.metric in metric_function_mapping:
        try:
            return metric_function_mapping[gauge.metric](gauge)
        except:  # noqa: E722
            pass


def _get_number_of_cases(gauge):
    case_type = gauge.case_type
    domain = gauge.dashboard.domain
    case_es_query = CaseSearchES().domain(domain)
    if case_type:
        case_es_query = case_es_query.case_type(case_type)
    if gauge.case_query:
        case_es_query = case_es_query.xpath_query(domain, gauge.case_query)
    return case_es_query.count()


def _get_number_of_mobile_workers(gauge):
    return UserES().domain(gauge.dashboard.domain).mobile_users().count()


def _get_number_of_active_mobile_workers(gauge):
    return UserES().domain(gauge.dashboard.domain).mobile_users().is_active().count()


def _get_number_of_inactive_mobile_workers(gauge):
    return UserES().domain(gauge.dashboard.domain).mobile_users().is_active(active=False).count()


def _get_number_of_forms_submitted_by_mobile_workers(gauge):
    return FormES().domain(gauge.dashboard.domain).user_type('mobile').count()


metric_function_mapping = {
    'number_of_cases': _get_number_of_cases,
    'number_of_mobile_workers': _get_number_of_mobile_workers,
    'number_of_active_mobile_workers': _get_number_of_active_mobile_workers,
    'number_of_inactive_mobile_workers': _get_number_of_inactive_mobile_workers,
    'number_of_forms_submitted_by_mobile_workers': _get_number_of_forms_submitted_by_mobile_workers,
}
