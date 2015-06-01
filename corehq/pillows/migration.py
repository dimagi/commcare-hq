from pillowtop.listener import BasicPillow
from couchforms.models import XFormInstanceDevicelog, XFormInstance
from .utils import get_deleted_doc_types


class MigrationPillow(BasicPillow):
    """
    The migration pillow is intended to be used for migrating couchdocs from one couch database to another.
    This should be used in combination of the couch_migrate command to initially seed the destination
    database:

    https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cleanup/management/commands/couch_migrate.py

    The pillow ensures that all documents that get deleted in the source database are subsequently updated in
    the destination database.
    """

    # Override this to determine what constitutes a deleted document
    # is_deleted = lambda doc: False

    # Override this function to get the db instance you'd like to migrate to
    dest_db = lambda: None

    def change_trigger(self, changes_dict):
        if changed_dict.get('deleted', False):
            self.dest_db().delete_doc(changed_dict['id'])
            return None
        # This seems to defe the purpose of making it a mixin...
        super(MigrationPillow, self).change_trigger(changes_dic)

    def change_transport(self, doc):
        self.dest_db().save(doc)


class DeviceLogMigrationPillow(MigrationPillow):
    couch_filter = 'couchforms/devicelogs'  # string for filter if needed
    document_class = XFormInstance
    dest_db = XFormInstanceDevicelog.get_db
