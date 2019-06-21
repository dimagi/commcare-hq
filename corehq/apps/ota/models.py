from __future__ import absolute_import
from __future__ import unicode_literals
import io
from collections import namedtuple

from django.db import models, transaction

from casexml.apps.phone.restore import stream_response
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.atomic import AtomicBlobs
from corehq.util.quickcache import quickcache
import six


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
    def create(cls, user_id, restore_content, domain):
        """
        The method to create a new DemoUserRestore object
        ags:
            user_id: the id of the CommCareUser
            restore_content: a string or file-like object of user's restore XML
        """
        restore = cls(
            demo_user_id=user_id,
            restore_comment="",
        )
        with AtomicBlobs(get_blob_db()) as db:
            restore._write_restore_blob(restore_content, db, domain)
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

    def get_restore_as_string(self):
        """
        Returns restore XML as a string
        """
        try:
            blob = self._get_restore_xml()
            return blob.read()
        finally:
            blob.close()

    def _get_restore_xml(self):
        return get_blob_db().get(key=self.restore_blob_id)

    def delete(self):
        """
        Deletes the restore object and the xml blob permenantly
        """
        get_blob_db().delete(key=self.restore_blob_id)
        super(DemoUserRestore, self).delete()

    def _write_restore_blob(self, restore, db, domain):

        if isinstance(restore, six.text_type):
            restore = io.BytesIO(restore.encode("utf-8"))
        elif isinstance(restore, bytes):
            restore = io.BytesIO(restore)

        meta = db.put(
            restore,
            domain=domain,
            parent_id=self.demo_user_id or "DemoUserRestore",
            type_code=CODES.demo_user_restore,
        )
        self.restore_blob_id = meta.key
        self.content_length = meta.content_length


class SerialIdBucket(models.Model):
    """
    Model used to keep track of an incrementing, unique integer
    to be used in serial ID generation
    """
    domain = models.CharField(max_length=255)
    bucket_id = models.CharField(max_length=255)
    current_value = models.IntegerField(default=-1)

    class Meta(object):
        index_together = ('domain', 'bucket_id',)
        unique_together = ('domain', 'bucket_id',)

    @classmethod
    def get_next(cls, domain, bucket_id, session_id=None):
        if session_id:
            return cls._get_next_cached(domain, bucket_id, session_id)
        else:
            return cls._get_next(domain, bucket_id)

    @classmethod
    @quickcache(['domain', 'bucket_id', 'session_id'])
    def _get_next_cached(cls, domain, bucket_id, session_id):
        return cls._get_next(domain, bucket_id)

    @classmethod
    @transaction.atomic
    def _get_next(cls, domain, bucket_id):
        # select_for_update locks matching rows until the end of the transaction
        bucket, _ = (cls.objects
                     .select_for_update()
                     .get_or_create(domain=domain, bucket_id=bucket_id))
        bucket.current_value += 1
        bucket.save()
        return bucket.current_value


Measure = namedtuple('Measure', 'slug name description')


class MobileRecoveryMeasure(models.Model):
    """
    Model representing a method of recovering from a fatal error on mobile.
    """
    MEASURES = (
        Measure('app_reinstall_and_update', "Reinstall and Update App",
                "Reinstall the current CommCare app either OTA or with a ccz, but "
                "requiring an OTA update to the latest version before it may be used."),
        Measure('app_update', "Update App",
                "Update the current CommCare app"),
        Measure('cc_reinstall', "CC Reinstall Needed",
                "Notify the user that CommCare needs to be reinstalled"),
        Measure('cc_update', "CC Update Needed",
                "Notify the user that CommCare needs to be updated"),
        Measure('app_offline_reinstall_and_update', "Offline Reinstall and Update App",
                "Reinstall the current CommCare app offline.")
    )
    measure = models.CharField(
        max_length=255,
        choices=[(m.slug, m.name) for m in MEASURES],
        help_text="<br/>".join(
            "<strong>{}:</strong> {}".format(m.name, m.description)
            for m in MEASURES
        )
    )

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=50)

    cc_all_versions = models.BooleanField(
        verbose_name="All CommCare Versions", default=True)
    cc_version_min = models.CharField(
        verbose_name="Min CommCare Version", max_length=255, blank=True)
    cc_version_max = models.CharField(
        verbose_name="Max CommCare Version", max_length=255, blank=True)

    app_all_versions = models.BooleanField(
        verbose_name="All App Versions", default=True)
    app_version_min = models.IntegerField(
        verbose_name="Min App Version", null=True, blank=True)
    app_version_max = models.IntegerField(
        verbose_name="Max App Version", null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    username = models.CharField(max_length=255, editable=False)
    notes = models.TextField(blank=True)

    @property
    def sequence_number(self):
        return self.pk

    def to_mobile_json(self):
        res = {
            "sequence_number": self.sequence_number,
            "type": self.measure,
        }
        if not self.cc_all_versions:
            res["cc_version_min"] = self.cc_version_min
            res["cc_version_max"] = self.cc_version_max
        if not self.app_all_versions:
            res["app_version_min"] = self.app_version_min
            res["app_version_max"] = self.app_version_max
        return res
