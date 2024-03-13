import importlib

from django.apps import AppConfig
from django.conf import settings


REPEATER_CLASS_MAP = {}


class RepeaterAppConfig(AppConfig):
    name = 'corehq.motech.repeaters'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import signals  # noqa: disable=unused-import,F401
        repeater_classes = settings.REPEATER_CLASSES
        for r_c in repeater_classes:
            module_name, _, class_name = r_c.rpartition('.')
            mod = importlib.import_module(module_name)
            if not REPEATER_CLASS_MAP.get(class_name):
                cls = getattr(mod, class_name)
                REPEATER_CLASS_MAP[class_name] = cls
