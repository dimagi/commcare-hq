from corehq.preindex import ExtraPreindexPlugin
from django.apps import AppConfig
from django.conf import settings


class AppManagerAppConfig(AppConfig):
    name = 'corehq.apps.app_manager'

    def ready(self):
        # Also sync this app's design docs to NEW_APPS_DB
        ExtraPreindexPlugin.register('app_manager', __file__, settings.NEW_APPS_DB)
