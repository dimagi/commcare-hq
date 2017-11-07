from __future__ import absolute_import
from corehq.preindex import ExtraPreindexPlugin
from django.conf import settings

ExtraPreindexPlugin.register('groups', __file__, settings.NEW_USERS_GROUPS_DB)
