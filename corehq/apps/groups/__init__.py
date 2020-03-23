from django.conf import settings

from corehq.preindex import ExtraPreindexPlugin

ExtraPreindexPlugin.register('groups', __file__, settings.USERS_GROUPS_DB)
