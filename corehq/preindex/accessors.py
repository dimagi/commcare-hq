from __future__ import absolute_import
from __future__ import unicode_literals
import os
from dimagi.utils.couch import sync_docs
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


def get_preindex_designs():
    used = set()
    designs = []
    for plugin in get_preindex_plugins():
        for design in plugin.get_designs():
            key = (design.db.uri, design.app_label)
            if key not in used:
                designs.append(design)
            used.add(key)
    return designs


def copy_design_doc(design, temp=None, delete=True):
    sync_docs.copy_designs(
        db=design.db,
        design_name=design.app_label,
        temp=temp,
        delete=delete,
    )


def sync_design_doc(design, temp=None):
    sync_docs.sync_design_docs(
        db=design.db,
        design_dir=design.design_path,
        design_name=design.app_label,
        temp=temp,
    )


def index_design_doc(design, wait=True):
    design_name = design.app_label
    docid = "_design/%s" % design_name
    sync_docs.index_design_docs(
        db=design.db,
        docid=docid,
        design_name=design_name,
        wait=wait
    )
