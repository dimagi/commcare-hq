from cStringIO import StringIO
from django.db import models

from casexml.apps.phone.restore import stream_response
from corehq.blobs import get_blob_db
from corehq.blobs.atomic import AtomicBlobs
from corehq.blobs.util import random_url_id
from corehq.blobs.exceptions import NotFound


class DemoUserRestore(models.Model):
    """
    This holds the frozen restore XML blob for a demo mobile worker
    """
    demo_user_id = models.CharField(max_length=255, default=None, db_index=True)
    restore_blob_id = models.CharField(max_length=255, default=None)
    content_length = models.IntegerField(null=True)
    timestamp_created = models.DateTimeField(auto_now=True)
    restore_comment = models.CharField(max_length=250, null=True, blank=True)

    @classmethod
    def create(cls, user_id, restore_content, comment=""):
        """
        The method to create a new DemoUserRestore object
        ags:
            user_id: the id of the CommCareUser
            restore_content: a string or file-like object of user's restore XML
        """
        restore = cls(
            demo_user_id=user_id,
            restore_comment=comment,
        )
        with AtomicBlobs(get_blob_db()) as db:
            restore._write_restore_blob(restore_content, db)
            restore.save()
        return restore

    def get_restore_http_response(self):
        """
        Returns restore XML as a streaming http response
        """
        payload = self._get_restore_xml()
        headers = {
            'Content-Length': self.content_length,
            'Content-Type': 'text/xml'
        }
        return stream_response(payload, headers)

    def _get_restore_xml(self):
        db = get_blob_db()
        try:
            blob = db.get(self.restore_blob_id)
        except (KeyError, NotFound) as e:
            # Todo - custom exception
            raise e
        return blob

    def delete(self):
        """
        Deletes the restore object and the xml blob permenantly
        """
        self._delete_restore_blob()
        super(DemoUserRestore, self).delete()

    def _write_restore_blob(self, restore, db):

        if isinstance(restore, unicode):
            restore = StringIO(restore.encode("utf-8"))
        elif isinstance(restore, bytes):
            restore = StringIO(restore)

        info = db.put(restore, random_url_id(16))
        self.restore_blob_id = info.identifier
        self.content_length = info.length

    def _delete_restore_blob(self):
        db = get_blob_db()
        deleted = db.delete(self.restore_blob_id)
        self.restore_blob_id = None

        return deleted
