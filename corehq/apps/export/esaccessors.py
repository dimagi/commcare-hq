from corehq.apps.es import CaseES
from corehq.apps.es import FormES


def get_form_export_base_query(domain, app_id, xmlns):
    return (FormES()
            .domain(domain)
            .app(app_id)
            .xmlns(xmlns)
            .sort("received_on"))


def get_case_export_base_query(domain, case_type):
    return (CaseES()
            .domain(domain)
            .case_type(case_type)
            .sort("opened_on"))
