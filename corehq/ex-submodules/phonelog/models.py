from couchdbkit.ext.django.schema import Document
from dimagi.utils.decorators.memoized import memoized
from django.db import models

COUCH_UUID_MAX_LEN = 50


class Log(models.Model):
    xform_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True)
    msg = models.TextField()
    id = models.CharField(max_length=50, primary_key=True)
    type = models.CharField(max_length=32, db_index=True)
    date = models.DateTimeField(db_index=True)
    domain = models.CharField(max_length=100, db_index=True)
    device_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True)
    app_version = models.TextField()
    username = models.CharField(max_length=100, db_index=True)

    @property
    @memoized
    def device_users(self):
        return UserLog.objects.filter(xform_id__exact=self.xform_id)


class UserLog(models.Model):
    xform_id = models.CharField(max_length=COUCH_UUID_MAX_LEN, db_index=True)
    user_id = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    sync_token = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    username = models.CharField(max_length=100, db_index=True)


class _(Document):
    pass
