# encoding: utf-8
from south.v2 import DataMigration
from corehq.apps.app_manager.migrations import AppFilterMigrationMixIn


class Migration(AppFilterMigrationMixIn, DataMigration):

    def get_app_ids(self):
        return self._get_main_app_ids()
