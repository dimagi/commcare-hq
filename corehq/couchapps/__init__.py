from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta',
    'users_extra': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
    'noneulized_users': (settings.USERS_GROUPS_DB, settings.NEW_USERS_GROUPS_DB),
})
