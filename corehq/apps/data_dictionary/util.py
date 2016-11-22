from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.export.models.new import CaseExportDataSchema


def generate_data_dictionary(domain):
    current_case_types, current_properties = _get_current_case_types_and_properties(domain)

    properties = _get_all_case_properties(domain)
    new_case_properties = []
    for case_type, properties in properties.items():
        if not case_type:
            continue

        if case_type in current_case_types:
            case_type_obj = current_case_types[case_type]
        else:
            case_type_obj = CaseType.objects.create(domain=domain, name=case_type)

        for prop in properties:
            if (case_type not in current_properties or
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


def _get_current_case_types_and_properties(domain):
    properties = {}
    case_types = {}

    db_case_types = CaseType.objects.filter(domain=domain).prefetch_related('properties')
    for case_type in db_case_types:
        case_types[case_type.name] = case_type
        properties[case_type.name] = set()
        for prop in case_type.properties.all():
            case_type = prop.case_type.name
            properties[case_type].add(prop.name)

    return case_types, properties


def add_properties_to_data_dictionary(domain, case_type, properties):
    case_type_obj, created = CaseType.objects.get_or_create(domain=domain, name=case_type)
    if not created:
        old_properties = CaseProperty.objects.filter(case_type=case_type_obj)
        old_properties = {p.name for p in old_properties}
    else:
        old_properties = set()
    new_properties = []

    for case_property in properties:
        if case_property not in old_properties:
            old_properties.add(case_property)
            new_properties.append(CaseProperty(name=case_property, case_type=case_type_obj))

    CaseProperty.objects.bulk_create(new_properties)
