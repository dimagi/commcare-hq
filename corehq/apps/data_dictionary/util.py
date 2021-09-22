from itertools import groupby
from operator import attrgetter

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext

from corehq.apps.app_manager.app_schemas.case_properties import (
    all_case_properties_by_domain,
)
from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.data_dictionary.models import CaseProperty, CasePropertyAllowedValue, CaseType
from corehq.motech.fhir.utils import update_fhir_resource_property
from corehq.util.quickcache import quickcache


class OldExportsEnabledException(Exception):
    pass


def generate_data_dictionary(domain):
    properties = _get_all_case_properties(domain)
    _create_properties_for_case_types(domain, properties)
    CaseType.objects.filter(domain=domain, name__in=list(properties)).update(fully_generated=True)
    return True


def _get_all_case_properties(domain):
    # moved here to avoid circular import
    from corehq.apps.export.models.new import CaseExportDataSchema

    case_type_to_properties = {}
    case_properties_from_apps = all_case_properties_by_domain(
        domain, include_parent_properties=False
    )

    for case_type in get_case_types_from_apps(domain):
        properties = set()
        schema = CaseExportDataSchema.generate_schema_from_builds(domain, None, case_type)

        # only the first schema contains case properties. The others contain meta info
        group_schema = schema.group_schemas[0]
        for item in group_schema.items:
            if len(item.path) > 1:
                continue

            if item.tag:
                name = item.tag
            else:
                name = item.path[-1].name

            if '/' not in name:
                # Filter out index and parent properties as some are stored as parent/prop in item.path
                properties.add(name)

        case_type_props_from_app = case_properties_from_apps.get(case_type, {})
        properties |= set(case_type_props_from_app)

        case_type_to_properties[case_type] = properties

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
    if properties:
        _create_properties_for_case_types(domain, {case_type: properties})


def _create_properties_for_case_types(domain, case_type_to_prop):
    current_case_types, current_properties = _get_current_case_types_and_properties(domain)
    new_case_properties = []

    for case_type, props in case_type_to_prop.items():
        if not case_type:
            continue

        try:
            case_type_obj = current_case_types[case_type]
        except KeyError:
            case_type_obj = CaseType.objects.create(domain=domain, name=case_type)

        for prop in props:
            # don't add any properites to parent cases
            if '/' in prop:
                continue

            if (case_type not in current_properties or
                    prop not in current_properties[case_type]):
                new_case_properties.append(CaseProperty(
                    case_type=case_type_obj, name=prop
                ))

    CaseProperty.objects.bulk_create(new_case_properties)


def get_case_property_description_dict(domain):
    """
    This returns a dictionary of the structure
    {
        case_type: {
                        case_property: description,
                        ...
                    },
        ...
    }
    for each case type and case property in the domain.
    """
    annotated_types = CaseType.objects.filter(domain=domain).prefetch_related('properties')
    descriptions_dict = {}
    for case_type in annotated_types:
        descriptions_dict[case_type.name] = {prop.name: prop.description for prop in case_type.properties.all()}
    return descriptions_dict


def save_case_property(name, case_type, domain=None, data_type=None,
                       description=None, group=None, deprecated=None,
                       fhir_resource_prop_path=None, fhir_resource_type=None, remove_path=False,
                       allowed_values=None):
    """
    Takes a case property to update and returns an error if there was one
    """
    if not name:
        return ugettext('Case property must have a name')

    prop = CaseProperty.get_or_create(
        name=name, case_type=case_type, domain=domain
    )
    if data_type:
        prop.data_type = data_type
    if description:
        prop.description = description
    if group:
        prop.group = group
    if deprecated is not None:
        prop.deprecated = deprecated
    try:
        prop.full_clean()
    except ValidationError as e:
        return str(e)

    if fhir_resource_type and fhir_resource_prop_path:
        update_fhir_resource_property(prop, fhir_resource_type, fhir_resource_prop_path, remove_path)
    prop.save()

    # If caller has supplied non-None value for allowed_values, then
    # synchronize the supplied dict (key=allowed_value, value=description)
    # with the database stored values for this property.
    err_cnt = 0
    max_len = CasePropertyAllowedValue._meta.get_field('allowed_value').max_length
    if allowed_values is not None:
        obj_pks = []
        for allowed_value, av_desc in allowed_values.items():
            if len(allowed_value) > max_len:
                err_cnt += 1
            else:
                av_obj, _ = CasePropertyAllowedValue.objects.update_or_create(
                    case_property=prop, allowed_value=allowed_value, defaults={"description": av_desc})
                obj_pks.append(av_obj.pk)
        # Delete any database-resident allowed values that were not found in
        # the set supplied by caller.
        prop.allowed_values.exclude(pk__in=obj_pks).delete()

    if err_cnt:
        return ugettext('Unable to save valid values longer than {} characters').format(max_len)


@quickcache(vary_on=['domain'], timeout=24 * 60 * 60)
def get_data_dict_props_by_case_type(domain):
    return {
        case_type: {prop.name for prop in props} for case_type, props in groupby(
            CaseProperty.objects
            .filter(case_type__domain=domain, deprecated=False)
            .select_related("case_type")
            .order_by('case_type__name'),
            key=attrgetter('case_type.name')
        )
    }


@quickcache(vary_on=['domain'], timeout=24 * 60 * 60)
def get_data_dict_case_types(domain):
    case_types = CaseType.objects.filter(domain=domain).values_list('name', flat=True)
    return set(case_types)


def fields_to_validate(domain, case_type_name):
    filter_kwargs = {
        'case_type__domain': domain,
        'case_type__name': case_type_name,
        'data_type__in': ['date', 'select'],
    }
    props = CaseProperty.objects.filter(**filter_kwargs)
    return {prop.name: prop for prop in props}
