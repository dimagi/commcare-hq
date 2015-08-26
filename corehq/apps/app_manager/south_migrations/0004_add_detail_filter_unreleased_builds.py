# encoding: utf-8
from south.v2 import DataMigration
from corehq.apps.app_manager.south_migrations import AppFilterMigrationMixIn


class Migration(AppFilterMigrationMixIn, DataMigration):

    def get_app_ids(self):
        return self._get_all_app_ids()
