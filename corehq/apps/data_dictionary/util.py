from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.export.models.new import CaseExportDataSchema


def generate_data_dictionary(domain):
    current_properties = {}
    if CaseType.objects.filter(domain=domain).count() != 0:
        props = CaseProperty.objects.filter(case_type__domain=domain).prefetch_related('case_type')
        for prop in props:
            case_type = prop.case_type.name
            if case_type not in current_properties:
                current_properties[case_type] = {prop.name}
            else:
                current_properties[case_type].add(prop.name)

    properties = _get_all_case_properties(domain)
    new_case_properties = []
    for case_type, properties in properties.items():
        if not case_type:
            continue

        case_type_obj, _ = CaseType.objects.get_or_create(domain=domain, name=case_type)

        for prop in properties:
            if (not current_properties or
                    case_type not in current_properties or
                    prop not in current_properties[case_type]):
                new_case_properties.append(CaseProperty(
                    case_type=case_type_obj, name=prop
                ))

    CaseProperty.objects.bulk_create(new_case_properties)


def _get_all_case_properties(domain):
    case_type_to_properties = {}

    for case_type in get_case_types_from_apps(domain):
        properties = set()
        schema = CaseExportDataSchema.generate_schema_from_builds(domain, None, case_type)
        for group_schema in schema.group_schemas:
            for item in group_schema.items:
                if item.tag:
                    name = item.tag
                else:
                    name = '/'.join([p.name for p in item.path])
                properties.add(name)

        case_type_to_properties[case_type] = list(properties)

    return case_type_to_properties
