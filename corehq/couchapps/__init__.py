from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta',
    'receiverwrapper': 'receiverwrapper',
    'users_extra': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'noneulized_users': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'all_docs': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.NEW_CASES_DB),
    'by_domain_doc_type_date': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.NEW_CASES_DB),
    'case_by_domain_hq_user_id_type': (settings.CASES_DB, settings.NEW_CASES_DB),
    'case_indices': (settings.CASES_DB, settings.NEW_CASES_DB),
    'cases_by_server_date': (settings.CASES_DB, settings.NEW_CASES_DB),
    'cases_get_lite': (settings.CASES_DB, settings.NEW_CASES_DB),
    'deleted_data': (settings.CASES_DB, settings.NEW_CASES_DB),
    'open_cases': (settings.CASES_DB, settings.NEW_CASES_DB),
})
