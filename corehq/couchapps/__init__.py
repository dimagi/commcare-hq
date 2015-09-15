from corehq.preindex import CouchAppsPreindexPlugin
from django.conf import settings

CouchAppsPreindexPlugin.register('couchapps', __file__, {
    'form_question_schema': 'meta',
    'groupexport': settings.USERS_GROUPS_DB,
    'users_extra': settings.USERS_GROUPS_DB,
})
