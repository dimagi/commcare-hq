from django.apps import AppConfig
from django.conf import settings

from corehq.extensions.signals import extensions_loaded


class ExtensionAppConfig(AppConfig):
    name = 'corehq.extensions'

    def ready(self):
        from corehq.extensions import extension_manager
        extension_manager.load_extensions(settings.COMMCARE_EXTENSIONS)
        extensions_loaded.send(self)
