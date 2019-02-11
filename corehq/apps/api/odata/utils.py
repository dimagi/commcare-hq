from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.export.models import CaseExportDataSchema
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es


def get_case_type_to_properties(domain):
    case_type_to_properties = {}
    case_types = get_case_types_for_domain_es(domain)
    for case_type in case_types:
        case_type_to_properties[case_type] = []
        case_export_schema = CaseExportDataSchema.generate_schema_from_builds(domain, None, case_type)
        for export_group_schema in case_export_schema.group_schemas[0].items:
            cleaned_case_property = export_group_schema.label.replace('_', '')
            case_type_to_properties[case_type].append(cleaned_case_property)
    return case_type_to_properties
