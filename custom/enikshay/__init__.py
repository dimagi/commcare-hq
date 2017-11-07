from __future__ import absolute_import
from django.apps import AppConfig


class EnikshayAppConfig(AppConfig):
    name = 'custom.enikshay'

    def ready(self):
        from .user_setup import connect_signals
        connect_signals()


default_app_config = 'custom.enikshay.EnikshayAppConfig'
