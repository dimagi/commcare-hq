from corehq.preindex import ExtraPreindexPlugin
from django.apps import AppConfig
from django.conf import settings

from .users.signals import connect_signals


class EnikshayAppConfig(AppConfig):
    name = 'custom.enikshay'

    def ready(self):
        connect_signals()


default_app_config = 'custom.enikshay.EnikshayAppConfig'
