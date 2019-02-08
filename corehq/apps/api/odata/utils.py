from corehq.apps.app_manager.app_schemas.case_properties import ParentCasePropertyBuilder
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es


def get_case_type_to_properties(domain):
    # TODO - use CaseExportDataSchema
    apps = get_apps_in_domain(domain)
    case_types = get_case_types_for_domain_es(domain)
    return {
        k: map(lambda x: x.replace('_', ''), v)
        for k, v in ParentCasePropertyBuilder(domain, apps).get_case_property_map(case_types).items()
    }
