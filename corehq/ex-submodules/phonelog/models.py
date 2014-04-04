from couchdbkit.ext.django.schema import Document
from dimagi.utils.decorators.memoized import memoized
from django.db import models

COUCH_UUID_MAX_LEN = 50


class DeviceReportEntry(models.Model):
    xform_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True)
    i = models.IntegerField()
    msg = models.TextField()
    type = models.CharField(max_length=32, db_index=True)
    date = models.DateTimeField(db_index=True)
    domain = models.CharField(max_length=100, db_index=True)
    device_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True,
                                 null=True)
    app_version = models.TextField(null=True)
    username = models.CharField(max_length=100, db_index=True, null=True)

    class Meta:
        unique_together = [('xform_id', 'i')]

    @property
    @memoized
    def device_users(self):
        return list(
            UserEntry.objects.filter(xform_id__exact=self.xform_id)
            .distinct('username').values_list('username', flat=True)
        )


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
