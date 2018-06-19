from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models

from corehq.blobs import get_blob_db

ICDS_BUCKET = 'icds_blobdb'
EXPIRED = 60 * 60 * 24 * 7  # 7 days


class IcdsMonths(models.Model):
    month_name = models.TextField(primary_key=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'icds_months'


class IcdsFile(models.Model):
    blob_id = models.CharField(max_length=255)
    data_type = models.CharField(max_length=255)
    file_added = models.DateField(auto_now=True)

    def store_file_in_blobdb(self, file):
        blob_db = get_blob_db()
        blob_db.put(file, self.blob_id, bucket=ICDS_BUCKET, timeout=EXPIRED)

    def get_file_from_blobdb(self):
        blob_db = get_blob_db()
        return blob_db.get(self.blob_id, ICDS_BUCKET)

    class Meta:
        app_label = 'icds_reports'
