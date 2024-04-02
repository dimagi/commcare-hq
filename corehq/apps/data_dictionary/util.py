from collections import defaultdict
from itertools import groupby
from operator import attrgetter
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from corehq.apps.app_manager.app_schemas.case_properties import (
    all_case_properties_by_domain,
)
from corehq.apps.app_manager.dbaccessors import get_case_types_from_apps
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CasePropertyGroup,
    CaseType,
)
from corehq.apps.es.aggregations import NestedAggregation, TermsAggregation
from corehq.apps.es.case_search import CaseSearchES, CASE_PROPERTIES_PATH, PROPERTY_KEY
from corehq.motech.fhir.utils import update_fhir_resource_property
from corehq.util.quickcache import quickcache


def generate_data_dictionary(domain):
    case_type_to_properties = _get_all_case_properties(domain)
    _create_properties_for_case_types(domain, case_type_to_properties)
    CaseType.objects.filter(domain=domain, name__in=list(case_type_to_properties)).update(fully_generated=True)
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

            name = item.tag if item.tag else item.path[-1].name
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

            if (case_type not in current_properties
                    or prop not in current_properties[case_type]):
                new_case_properties.append(CaseProperty(
                    case_type=case_type_obj, name=prop
                ))

    CaseProperty.objects.bulk_create(new_case_properties)

    for case_type, props in case_type_to_prop.items():
        if case_type:
            CaseProperty.clear_caches(domain, case_type)


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


def get_case_property_label_dict(domain):
    """
    This returns a dictionary of the structure
    {
        case_type: {
                        case_property: label,
                        ...
                    },
        ...
    }
    for each case type and case property in the domain.
    """
    annotated_types = CaseType.objects.filter(domain=domain).prefetch_related('properties')
    labels_dict = {}
    for case_type in annotated_types:
        labels_dict[case_type.name] = {prop.name: prop.label for prop in case_type.properties.all()}
    return labels_dict


def get_values_hints_dict(domain, case_type_name):
    values_hints_dict = defaultdict(list)
    case_type = CaseType.objects.filter(domain=domain, name=case_type_name).first()
    if case_type:
        for prop in case_type.properties.all():
            if prop.data_type == 'date':
                values_hints_dict[prop.name] = [gettext('YYYY-MM-DD')]
            elif prop.data_type == 'select':
                values_hints_dict[prop.name] = [av.allowed_value for av in prop.allowed_values.all()]
    return values_hints_dict


def get_deprecated_fields(domain, case_type_name):
    deprecated_fields = set()
    case_type = CaseType.objects.filter(domain=domain, name=case_type_name).first()
    if case_type:
        deprecated_fields = set(case_type.properties.filter(deprecated=True).values_list('name', flat=True))
    return deprecated_fields


def save_case_property_group(id, name, case_type, domain, description, index, deprecated):
    """
    Takes a case property group to update and returns an error if there was one
    """
    if not name:
        return gettext('Case Property Group must have a name')

    case_type_obj = CaseType.objects.get(domain=domain, name=case_type)
    if id is not None:
        group = CasePropertyGroup.objects.get(id=id, case_type=case_type_obj)
    else:
        group = CasePropertyGroup(case_type=case_type_obj)

    group.name = name
    if description is not None:
        group.description = description
    if index is not None:
        group.index = index
    if deprecated is not None:
        group.deprecated = deprecated

    try:
        group.full_clean(validate_unique=True)
    except ValidationError as e:
        return str(e)

    group.save()


def save_case_property(name, case_type, domain=None, data_type=None,
                       description=None, label=None, group=None, deprecated=None,
                       fhir_resource_prop_path=None, fhir_resource_type=None, remove_path=False,
                       allowed_values=None, index=None):
    """
    Takes a case property to update and returns an error if there was one
    """
    if not name:
        return gettext('Case property must have a name')
    if not is_case_type_or_prop_name_valid(name):
        return gettext('Invalid case property name. It should start with a letter, and only contain letters, '
                       'numbers, "-", and "_"')

    try:
        prop = CaseProperty.get_or_create(
            name=name, case_type=case_type, domain=domain
        )
    except ValueError as e:
        return str(e)

    prop.data_type = data_type if data_type else ""
    if description is not None:
        prop.description = description

    if group:
        prop.group, created = CasePropertyGroup.objects.get_or_create(name=group, case_type=prop.case_type)
    else:
        prop.group = None

    if deprecated is not None:
        prop.deprecated = deprecated
    if label is not None:
        prop.label = label
    if index is not None:
        prop.index = index
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
        return gettext('Unable to save valid values longer than {} characters').format(max_len)


def delete_case_property(name, case_type, domain):
    try:
        prop = CaseProperty.objects.get(name=name, case_type__name=case_type, case_type__domain=domain)
    except CaseProperty.DoesNotExist:
        return gettext('Case property does not exist.')
    prop.delete()


@quickcache(vary_on=['domain', 'exclude_deprecated'], timeout=24 * 60 * 60)
def get_data_dict_props_by_case_type(domain, exclude_deprecated=True):
    filter_kwargs = {'case_type__domain': domain}
    if exclude_deprecated:
        filter_kwargs['deprecated'] = False
    return {
        case_type: {prop.name for prop in props} for case_type, props in groupby(
            CaseProperty.objects
            .filter(**filter_kwargs)
            .select_related("case_type")
            .order_by('case_type__name'),
            key=attrgetter('case_type.name')
        )
    }


@quickcache(vary_on=['domain'], timeout=24 * 60 * 60)
def get_data_dict_case_types(domain):
    case_types = CaseType.objects.filter(domain=domain).values_list('name', flat=True)
    return set(case_types)


def get_data_dict_deprecated_case_types(domain):
    case_types = CaseType.objects.filter(domain=domain, is_deprecated=True).values_list('name', flat=True)
    return set(case_types)


def fields_to_validate(domain, case_type_name):
    filter_kwargs = {
        'case_type__domain': domain,
        'case_type__name': case_type_name,
        'data_type__in': ['date', 'select'],
    }
    props = CaseProperty.objects.filter(**filter_kwargs)
    return {prop.name: prop for prop in props}


@quickcache(['domain', 'case_type'], timeout=24 * 60 * 60)
def get_gps_properties(domain, case_type):
    return set(CaseProperty.objects.filter(
        case_type__domain=domain,
        case_type__name=case_type,
        data_type=CaseProperty.DataType.GPS,
    ).values_list('name', flat=True))


def get_column_headings(row, valid_values, sheet_name, case_prop_name=None):
    column_headings = []
    errors = []
    for index, cell in enumerate(row, start=1):
        if not cell.value:
            errors.append(
                _("Column {} in \"{}\" sheet has an empty header").format(index, sheet_name)
            )
            continue

        cell_value = cell.value.lower()
        if cell_value in valid_values:
            column_headings.append(valid_values[cell_value])
        else:
            formatted_valid_values = ', '.join(list(valid_values.keys())).title()
            error = _("Invalid column \"{}\" in \"{}\" sheet. Valid column names are: {}").format(
                cell.value, sheet_name, formatted_valid_values)
            errors.append(error)
    if case_prop_name and case_prop_name not in column_headings:
        errors.append(
            _("Missing \"Case Property\" column header in \"{}\" sheet").format(sheet_name)
        )

    return column_headings, errors


def map_row_values_to_column_names(row, column_headings, default_val=None):
    row_vals = defaultdict(lambda: default_val)
    for index, cell in enumerate(row):
        column_name = column_headings[index]
        cell_val = '' if cell.value is None else str(cell.value)
        row_vals[column_name] = cell_val
    return row_vals


def is_case_type_deprecated(domain, case_type):
    try:
        case_type_obj = CaseType.objects.get(domain=domain, name=case_type)
        return case_type_obj.is_deprecated
    except CaseType.DoesNotExist:
        return False


def is_case_type_or_prop_name_valid(case_prop_name):
    pattern = '^[a-zA-Z][a-zA-Z0-9-_]*$'
    match_obj = re.match(pattern, case_prop_name)
    return match_obj is not None


@quickcache(vary_on=['domain'], timeout=60 * 10)
def get_used_props_by_case_type(domain):
    agg = TermsAggregation('case_types', 'type.exact').aggregation(
        NestedAggregation('case_props', CASE_PROPERTIES_PATH).aggregation(
            TermsAggregation('props', PROPERTY_KEY)
        )
    )
    query = (
        CaseSearchES()
        .domain(domain)
        .size(0)
        .aggregation(agg)
    )
    case_type_buckets = query.run().aggregations.case_types.buckets_list
    props_by_case_type = {}
    for case_type_bucket in case_type_buckets:
        prop_buckets = case_type_bucket.case_props.props.buckets_list
        for prop_bucket in prop_buckets:
            if case_type_bucket.key not in props_by_case_type:
                props_by_case_type[case_type_bucket.key] = []
            props_by_case_type[case_type_bucket.key].append(prop_bucket.key)
    return props_by_case_type
