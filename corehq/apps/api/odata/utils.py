from __future__ import absolute_import
from __future__ import unicode_literals

from six.moves import map

from corehq.apps.app_manager.app_schemas.case_properties import ParentCasePropertyBuilder
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es


def get_case_type_to_properties(domain):
    # TODO - use CaseExportDataSchema
    apps = get_apps_in_domain(domain)
    case_types = get_case_types_for_domain_es(domain)
    return {
        case_type: [case_property.replace('_', '') for case_property in case_properties]
        for case_type, case_properties in
        ParentCasePropertyBuilder(domain, apps).get_case_property_map(case_types).items()
    }
