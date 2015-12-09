import os
from django.apps import apps
from corehq.preindex import PreindexPlugin
from corehq.util.couchdb_management import couch_config
from dimagi.utils.couch.sync_docs import DesignInfo


class DefaultPreindexPlugin(PreindexPlugin):
    def __init__(self, app_label):
        self.app_label = app_label

    def get_designs(self):
        app_config = apps.get_app_config(self.app_label)
        return [
            DesignInfo(app_label=app_config.label,
                       db=couch_config.get_db_for_app_label(app_config.label),
                       design_path=os.path.join(app_config.path, '_design'))
        ]
