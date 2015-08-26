from dimagi.ext.couchdbkit import Document
from django.db import models

COUCH_UUID_MAX_LEN = 50


class DeviceReportEntry(models.Model):
    xform_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True)
    i = models.IntegerField()
    msg = models.TextField()
    type = models.CharField(max_length=32, db_index=True)
    date = models.DateTimeField(db_index=True)
    server_date = models.DateTimeField(null=True, db_index=True)
    domain = models.CharField(max_length=100, db_index=True)
    device_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True,
                                 null=True)
    app_version = models.TextField(null=True)
    username = models.CharField(max_length=100, db_index=True, null=True)
    user_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True, null=True)

    class Meta:
        unique_together = [('xform_id', 'i')]
        index_together = [
            ("domain", "date"),
        ]


class UserEntry(models.Model):
    xform_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True)
    i = models.IntegerField()
    user_id = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    sync_token = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    username = models.CharField(max_length=100, db_index=True)

    class Meta:
        unique_together = [('xform_id', 'i')]


class _(Document):
    pass
