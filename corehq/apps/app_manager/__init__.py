from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.preindex import ExtraPreindexPlugin
from django.apps import AppConfig
from django.conf import settings


class AppManagerAppConfig(AppConfig):
    name = 'corehq.apps.app_manager'

    def ready(self):
        # Also sync this app's design docs to NEW_APPS_DB
        ExtraPreindexPlugin.register('app_manager', __file__,
                                     (settings.APPS_DB, settings.NEW_APPS_DB))


default_app_config = 'corehq.apps.app_manager.AppManagerAppConfig'
