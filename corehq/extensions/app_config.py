from django.apps import AppConfig
from django.conf import settings


class ExtensionAppConfig(AppConfig):
    name = 'corehq.extensions'

    def ready(self):
        from corehq.extensions import extension_points, extension_manager  # noqa
        extension_manager.add_extension_points(extension_points)
        extension_manager.load_extensions(settings.COMMCARE_EXTENSIONS)
