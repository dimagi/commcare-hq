from corehq.apps.app_manager.management.commands.helpers import (
    AppMigrationCommandBase,
)
from corehq.apps.app_manager.util import get_correct_app_class
from datetime import datetime


class Command(AppMigrationCommandBase):
    help = "One-time migration to replace CaseSearch command_label and again_label with " \
           "search_label and search_again_label"

    chunk_size = 1
    include_builds = True
    include_linked_apps = True
    migration_date = '2018-02-1'
    default_date = '2017-01-01'

    def migrate_app(self, app_doc):
        should_save = False
        last_modified = app_doc.get('last_modified', self.default_date)
        should_save = last_modified < self.migration_date
        return get_correct_app_class(app_doc).wrap(app_doc) if should_save else None
