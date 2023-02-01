from django.apps import AppConfig
from django.conf import settings

from corehq.preindex import ExtraPreindexPlugin


class AppManagerAppConfig(AppConfig):
    name = 'corehq.apps.app_manager'

    def ready(self):
        # Also sync this app's design docs to APPS_DB
        ExtraPreindexPlugin.register('app_manager', __file__, settings.APPS_DB)
