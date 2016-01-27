from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta',
    'receiverwrapper': 'receiverwrapper',
    'users_extra': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'all_docs': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB),
    'by_domain_doc_type_date': (
        None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB, 'meta',
        settings.NEW_DOMAINS_DB, settings.SYNCLOGS_DB),
})
