from collections import namedtuple

from django.utils.translation import gettext as _

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.app_schemas.case_properties import all_case_properties_by_domain
from corehq.apps.case_search.const import METADATA_IN_REPORTS
from corehq.apps.data_cleaning.models import DataType
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.util.quickcache import quickcache

SKIPPED_SYSTEM_PROPERTIES = [
    'case_name',  # duplicate of `name`
]

EDITABLE_SYSTEM_PROPERTIES = [
    'external_id',
]

PropertyDetail = namedtuple('PropertyDetail', 'label data_type prop_id is_editable options')


def clear_caches_case_data_cleaning(domain, case_type=None):
    case_types = [case_type] if case_type else get_case_types_for_domain(domain)
    for case_type in case_types:
        all_case_properties_by_domain.clear(
            domain=domain,
            include_parent_properties=False,
            exclude_deprecated_properties=False,
        )
        get_case_property_details.clear(
            domain=domain,
            case_type=case_type,
        )


def get_system_property_data_type(prop_id):
    return {
        'date_opened': DataType.DATETIME,
        'closed_on': DataType.DATETIME,
        'last_modified': DataType.DATETIME,
        'server_last_modified_date': DataType.DATETIME,
    }.get(prop_id, DataType.TEXT)


def get_system_property_label(prop_id):
    return {
        '@case_id': _("Case ID"),
        '@case_type': _("Case Type"),
        '@owner_id': _("Owner ID"),
        '@status': _("Open/Closed Status"),
        'name': _("Name"),
        'external_id': _("External ID"),
        'date_opened': _("Date Opened"),
        'closed_on': _("Closed On"),
        'last_modified': _("Last Modified On"),
        'closed_by_username': _("Closed By"),
        'last_modified_by_user_username': _("Last Modified By"),
        'opened_by_username': _("Opened By"),
        'owner_name': _("Owner"),
        'closed_by_user_id': _("Closed By User ID"),
        'opened_by_user_id': _("Opened By User ID"),
        'server_last_modified_date': _("Last Modified (UTC)"),
    }.get(prop_id, prop_id)


def _get_system_property_details():
    system_properties = {}
    for prop_id in METADATA_IN_REPORTS:
        if prop_id in SKIPPED_SYSTEM_PROPERTIES:
            continue
        system_properties[prop_id] = PropertyDetail(
            label=get_system_property_label(prop_id),
            data_type=get_system_property_data_type(prop_id),
            prop_id=prop_id,
            is_editable=prop_id in EDITABLE_SYSTEM_PROPERTIES,
            options=None,
        )._asdict()
    return system_properties


def _get_data_type_from_data_dictionary(case_property):
    from corehq.apps.data_dictionary.models import CaseProperty
    return {
        CaseProperty.DataType.DATE: DataType.DATE,
        CaseProperty.DataType.PLAIN: DataType.TEXT,
        # todo, Data Dictionary should support Integer and Decimal:
        CaseProperty.DataType.NUMBER: DataType.INTEGER,
        CaseProperty.DataType.SELECT: DataType.MULTIPLE_OPTION,
        CaseProperty.DataType.BARCODE: DataType.BARCODE,
        CaseProperty.DataType.GPS: DataType.GPS,
        CaseProperty.DataType.PHONE_NUMBER: DataType.PHONE_NUMBER,
        CaseProperty.DataType.PASSWORD: DataType.PASSWORD,
    }.get(case_property.data_type, DataType.TEXT)


def _get_default_label(prop_id):
    return prop_id.replace('_', ' ').title()


def _get_property_details_from_data_dictionary(domain, case_type):
    if not domain_has_privilege(domain, privileges.DATA_DICTIONARY):
        return {}
    from corehq.apps.data_dictionary.models import CaseType
    try:
        case_properties = CaseType.objects.get(domain=domain, name=case_type).properties.all()
        details = {}
        for case_property in case_properties:
            details[case_property.name] = PropertyDetail(
                label=case_property.label or _get_default_label(case_property.name),
                data_type=_get_data_type_from_data_dictionary(case_property),
                prop_id=case_property.name,
                is_editable=True,
                options=list(case_property.allowed_values.values_list('allowed_value', flat=True)),
            )._asdict()
        return details
    except CaseType.DoesNotExist:
        return {}


@quickcache(vary_on=['domain', 'case_type'])
def get_case_property_details(domain, case_type):
    details = {}
    properties = all_case_properties_by_domain(
        domain,
        include_parent_properties=False,
        exclude_deprecated_properties=False,
    ).get(case_type, [])
    data_dictionary_details = _get_property_details_from_data_dictionary(domain, case_type)
    properties = set(properties).union(data_dictionary_details.keys())
    for prop_id in properties:
        details[prop_id] = data_dictionary_details.get(
            prop_id, PropertyDetail(
                label=_get_default_label(prop_id),
                data_type=DataType.TEXT,
                prop_id=prop_id,
                is_editable=True,
                options=None,
            )._asdict()
        )
    details.update(_get_system_property_details())
    return details
