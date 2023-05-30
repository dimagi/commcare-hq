from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'schemas_by_xmlns_or_case_type': settings.META_DB,
    'export_instances_by_domain': settings.META_DB,
    'export_instances_by_is_daily_saved': settings.META_DB,
    'receiverwrapper': 'receiverwrapper',
    'users_extra': settings.USERS_GROUPS_DB,
    'deleted_users_by_username': settings.USERS_GROUPS_DB,
    'all_docs': (
        None, settings.USERS_GROUPS_DB, settings.META_DB,
        settings.DOMAINS_DB, settings.APPS_DB),
    'by_domain_doc_type_date': (
        None, settings.USERS_GROUPS_DB, settings.META_DB,
        settings.DOMAINS_DB, settings.APPS_DB),
    'last_modified': (settings.USERS_GROUPS_DB, settings.DOMAINS_DB, settings.APPS_DB),

    'app_translations_by_popularity': settings.APPS_DB,
    'exports_forms_by_app': settings.APPS_DB,
    'forms_by_app_info': settings.APPS_DB,
    'apps_with_submissions': settings.APPS_DB,
    'saved_apps_auto_generated': settings.APPS_DB,
    'registry_data_sources': settings.META_DB,
    'registry_data_sources_by_last_modified': settings.META_DB,
    'registry_report_configs': settings.META_DB,
})
