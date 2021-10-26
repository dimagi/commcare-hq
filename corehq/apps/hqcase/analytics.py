from corehq.apps.es import CaseES


def get_number_of_cases_in_domain(domain):
    return CaseES().domain(domain).count()
