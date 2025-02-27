from django.http import Http404

from couchdbkit import ResourceNotFound

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.export.const import (
    DEID_DATE_TRANSFORM, DEID_ID_TRANSFORM, DEID_TRANSFORM_FUNCTIONS
)
from corehq.privileges import DAILY_SAVED_EXPORT, DEFAULT_EXPORT_SETTINGS, EXCEL_DASHBOARD
from corehq.toggles import MESSAGE_LOG_METADATA


def is_occurrence_deleted(last_occurrences, app_ids_and_versions):
    is_deleted = True
    for app_id, version in app_ids_and_versions.items():
        occurrence = last_occurrences.get(app_id)
        if occurrence is not None and occurrence >= version:
            is_deleted = False
            break
    return is_deleted


def domain_has_excel_dashboard_access(domain):
    return domain_has_privilege(domain, EXCEL_DASHBOARD)


def domain_has_daily_saved_export_access(domain):
    return domain_has_privilege(domain, DAILY_SAVED_EXPORT)


def get_export(export_type, domain, export_id=None, username=None):
    from corehq.apps.export.models import (
        FormExportInstance,
        CaseExportInstance,
        SMSExportInstance,
        SMSExportDataSchema
    )
    if export_type == 'form':
        try:
            return FormExportInstance.get(export_id)
        except ResourceNotFound:
            raise Http404()
    elif export_type == 'case':
        try:
            return CaseExportInstance.get(export_id)
        except ResourceNotFound:
            raise Http404()
    elif export_type == 'sms':
        if not username:
            raise Exception("Username needed to ensure permissions")
        include_metadata = MESSAGE_LOG_METADATA.enabled(username)
        return SMSExportInstance._new_from_schema(
            SMSExportDataSchema.get_latest_export_schema(domain, include_metadata)
        )
    raise Exception("Unexpected export type received %s" % export_type)


def get_default_export_settings_if_available(domain):
    """
    Only creates settings if the domain has the DEFAULT_EXPORT_SETTINGS privilege
    """
    from corehq.apps.accounting.models import Subscription
    settings = None
    current_subscription = Subscription.get_active_subscription_by_domain(domain)
    if current_subscription and domain_has_privilege(domain, DEFAULT_EXPORT_SETTINGS):
        from corehq.apps.export.models import DefaultExportSettings
        settings = DefaultExportSettings.objects.get_or_create(account=current_subscription.account)[0]

    return settings


def get_transform_function(func_name):
    import corehq.apps.export.transforms as module
    return getattr(module, func_name)


def get_deid_transform_function(func_name):
    if func_name == DEID_TRANSFORM_FUNCTIONS[DEID_DATE_TRANSFORM]:
        import couchexport.deid as module
        return getattr(module, func_name)
    elif func_name == DEID_TRANSFORM_FUNCTIONS[DEID_ID_TRANSFORM]:
        from corehq.apps.export.models import DeIdMapping
        return DeIdMapping.get_deid
