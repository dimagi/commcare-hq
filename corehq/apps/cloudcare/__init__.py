from corehq.preindex import ExtraPreindexPlugin
from django.apps import AppConfig
from django.conf import settings


class CloudcareAppConfig(AppConfig):
    name = 'corehq.apps.cloudcare'

    def ready(self):
        # Also sync this app's design docs to NEW_APPS_DB
        ExtraPreindexPlugin.register('cloudcare', __file__, settings.NEW_APPS_DB)


# constants
CLOUDCARE_DEVICE_ID = "cloudcare"
