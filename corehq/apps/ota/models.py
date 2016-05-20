from cStringIO import StringIO
from django.db import models

from casexml.apps.phone.restore import stream_response
from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound

import uuidfield


class DemoUserRestore(models.Model):
    uuid = uuidfield.UUIDField(unique=True, auto=True, db_index=True)
    demo_user_id = models.CharField(max_length=255, default=None, db_index=True)
    restore_blob_id = models.CharField(max_length=255, default=None, db_index=True)
    timestamp_created = models.DateTimeField(auto_now=True)
    restore_comment = models.CharField(max_length=250, null=True, blank=True)

    @classmethod
    def create(cls, user_id, restore_content, comment=""):
        restore = cls(
            demo_user_id=user_id,
            restore_comment=comment,
        )
        restore._write_restore_blob(restore_content)
        restore.save()
        return restore

    def get_restore_http_response(self):
        payload = self._get_restore_xml()
        headers = {}
        payload = StringIO(payload.encode("utf-8"))
        return stream_response(payload, headers)

    def _get_restore_xml(self):
        db = get_blob_db()
        try:
            blob = db.get(self.restore_blob_id)
        except (KeyError, NotFound) as e:
            # Todo - custom exception
            raise e

        with blob:
            return blob.read()

    def delete(self):
        self._delete_restore_blob()
        super(DemoUserRestore, self).delete()

    def _write_restore_blob(self, restore):

        if isinstance(restore, unicode):
            restore = StringIO(restore.encode("utf-8"))
        elif isinstance(restore, bytes):
            restore = StringIO(restore)

        db = get_blob_db()
        info = db.put(restore)
        self.restore_blob_id = info.identifier

    def _delete_restore_blob(self):
        db = get_blob_db()
        deleted = db.delete(self.restore_blob_id)
        if deleted:
            self.restore_blob_id = None

        return deleted
