from django.apps import AppConfig
from django.conf import settings

from corehq.preindex import ExtraPreindexPlugin


class AppManagerAppConfig(AppConfig):
    name = 'corehq.apps.app_manager'

    def ready(self):
        # Also sync this app's design docs to NEW_APPS_DB
        ExtraPreindexPlugin.register('app_manager', __file__,
                                     (settings.APPS_DB, settings.NEW_APPS_DB))


default_app_config = 'corehq.apps.app_manager.AppManagerAppConfig'
