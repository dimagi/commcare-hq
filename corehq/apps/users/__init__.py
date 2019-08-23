from corehq.preindex import ExtraPreindexPlugin
from django.apps import AppConfig
from django.conf import settings

from .signals import connect_user_signals


class UsersAppConfig(AppConfig):
    name = 'corehq.apps.users'

    def ready(self):
        """Code to run with Django starts"""
        ExtraPreindexPlugin.register('users', __file__, settings.NEW_USERS_GROUPS_DB)
        connect_user_signals()


default_app_config = 'corehq.apps.users.UsersAppConfig'
