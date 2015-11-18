from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta',
    'users_extra': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'noneulized_users': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'all_docs': (None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB),
    # TODO should we make an '_all' option or something?
    'by_domain_doc_type_date': (None, settings.NEW_USERS_GROUPS_DB, settings.NEW_FIXTURES_DB),
})
