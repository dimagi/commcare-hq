from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta',
    'schemas_by_xmlns_or_case_type': 'meta',
    'export_instances_by_domain': 'meta',
    'export_instances_by_is_daily_saved': 'meta',
    'receiverwrapper': 'receiverwrapper',
    'users_extra': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'all_docs': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.NEW_APPS_DB),
    'by_domain_doc_type_date': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.NEW_APPS_DB, settings.SYNCLOGS_DB),
    'domain_shows': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.NEW_APPS_DB, settings.SYNCLOGS_DB),
    # register these views to both the main db AND the apps db.
    'app_translations_by_popularity': (None, settings.NEW_APPS_DB),
    'exports_forms_by_app': (None, settings.NEW_APPS_DB),
    'forms_by_app_info': (None, settings.NEW_APPS_DB),
})
