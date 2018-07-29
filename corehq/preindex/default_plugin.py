from __future__ import absolute_import
from __future__ import unicode_literals
import os
from couchdbkit import Database
from django.apps import apps
from corehq.preindex import PreindexPlugin
from corehq.util.couchdb_management import CouchConfig
from dimagi.utils.couch.sync_docs import DesignInfo


class DefaultPreindexPlugin(PreindexPlugin):

    def __init__(self, app_label):
        self.app_label = app_label
        self.app_config = apps.get_app_config(self.app_label)
        self.dir = os.path.join(self.app_config.path, '_design')

    def _get_designs(self):
        # Instantiate here to make sure that it's instantiated after the dbs settings
        # are patched for tests
        couch_config = CouchConfig()
        db = Database(
            couch_config.get_db_uri_for_app_label(self.app_config.label), create=True)
        return [
            DesignInfo(app_label=self.app_config.label,
                       db=db,
                       design_path=self.dir)
        ]
