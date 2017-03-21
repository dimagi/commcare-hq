from django.apps import AppConfig
from .user_setup import connect_signals


class EnikshayAppConfig(AppConfig):
    name = 'custom.enikshay'

    def ready(self):
        connect_signals()


default_app_config = 'custom.enikshay.EnikshayAppConfig'
