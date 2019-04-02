from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta',
    'schemas_by_xmlns_or_case_type': 'meta',
    'export_instances_by_domain': 'meta',
    'export_instances_by_is_daily_saved': 'meta',
    'receiverwrapper': 'receiverwrapper',
    'users_extra': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'deleted_users_by_username': settings.USERS_GROUPS_DB,
    'all_docs': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.NEW_APPS_DB),
    'by_domain_doc_type_date': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.NEW_APPS_DB),
    'last_modified': (settings.USERS_GROUPS_DB, settings.DOMAINS_DB, settings.NEW_APPS_DB),

    'app_translations_by_popularity': settings.NEW_APPS_DB,
    'exports_forms_by_app': settings.NEW_APPS_DB,
    'forms_by_app_info': settings.NEW_APPS_DB,
    'apps_with_submissions': settings.NEW_APPS_DB,
    'saved_apps_auto_generated': settings.NEW_APPS_DB,
    'global_app_config_by_app_id': settings.NEW_APPS_DB,
})
