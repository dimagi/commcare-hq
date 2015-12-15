import os
from django.apps import apps
from corehq.preindex.default_plugin import DefaultPreindexPlugin
from corehq.preindex.preindex_plugins import PREINDEX_PLUGINS


def _is_eligible_for_default_plugin(app_config):
    if app_config.models_module:
        design_path = os.path.join(app_config.path, "_design")
        if os.path.isdir(design_path):
            return True
    return False


def get_preindex_plugins():
    app_labels = set(PREINDEX_PLUGINS)
    for app_config in apps.get_app_configs():
        if _is_eligible_for_default_plugin(app_config):
            app_labels.add(app_config.label)

    return [get_preindex_plugin(app_label) for app_label in sorted(app_labels)]


def get_preindex_plugin(app_label):
    try:
        return PREINDEX_PLUGINS[app_label]
    except KeyError:
        if _is_eligible_for_default_plugin(apps.get_app_config(app_label)):
            return DefaultPreindexPlugin(app_label)
        else:
            return None
