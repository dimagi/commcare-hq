import json
import os
import time

from django.conf import settings

from dimagi.ext.jsonobject import JsonObject, StringProperty, ListProperty
from dimagi.utils.couch.database import get_db
from pillowtop.listener import PythonPillow
from corehq.apps.domainsync.config import DocumentTransform, save
from corehq.apps.userreports.filters.factory import FilterFactory


class MigrationPillow(PythonPillow):
    """
    The migration pillow is intended to be used for migrating couchdocs from one couch database to another.
    This should be used in combination of the couch_migrate command to initially seed the destination
    database:

    https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cleanup/management/commands/couch_migrate.py

    The pillow ensures that all documents that get deleted in the source database are subsequently updated in
    the destination database.
    """

    # Override this with the config file supplied to the couch_migrate command
    config_file = None

    def __init__(self, *args, **kwargs):
        with open(self.config_file) as f:
            self.config = MigrationConfig.wrap(json.loads(f.read()))

        self.couch_db = self.config.source_db
        self.dest_db = self.config.dest_db
        if self.config.filters:
            self.filter_ = FilterFactory.from_spec(
                {
                    'type': 'and',
                    'filters': self.config.filters
                }
            )
        else:
            self.filter_ = None
        super(MigrationPillow, self).__init__(couch_db=self.couch_db)
        doc = self.get_checkpoint()
        self.is_migrating = doc.get('is_migrating', True)
        self.process_deletions = not doc.get('switched_dbs', False)

    def new_changes(self):
        checkpoint_doc = self.get_checkpoint()
        while checkpoint_doc.get('is_migrating', True):
            time.sleep(60)
            checkpoint_doc = self.get_checkpoint()
        self.is_migrating = False
        super(MigrationPillow, self).new_changes()

    def change_trigger(self, changes_dict):
        if not self.is_migrating:
            if changes_dict.get('deleted', False):
                self.dest_db.delete_doc(changes_dict['id'])
                return None
        return super(MigrationPillow, self).change_trigger(changes_dict)

    def change_transport(self, doc):
        if not self.is_migrating:
            dt = DocumentTransform(doc, self.couch_db)
            save(dt, self.dest_db)

    def python_filter(self, doc):
        if self.filter_:
            return self.filter_(doc)
        else:
            return True


class DevicelogMigrationPillow(MigrationPillow):
    config_file = os.path.join(
        settings.FILEPATH,
        'corehq/apps/cleanup/management/commands/couch_migrations/devicelogs.json',
    )


class MigrationConfig(JsonObject):
    from_db_postfix = StringProperty()
    to_db_postfix = StringProperty()
    doc_types = ListProperty(required=True)
    couch_views = ListProperty()
    filters = ListProperty()

    @property
    def source_db(self):
        return get_db(self.from_db_postfix)

    @property
    def dest_db(self):
        return get_db(self.to_db_postfix)
