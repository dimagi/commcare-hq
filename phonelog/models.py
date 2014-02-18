from django.db import models

COUCH_UUID_MAX_LEN = 50

class Log(models.Model):
    xform_id = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    msg = models.TextField()
    id = models.CharField(max_length=50, primary_key=True)
    type = models.CharField(max_length=32)
    date = models.DateTimeField()
    domain = models.CharField(max_length=100)
    device_id = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    app_version = models.TextField()
    username = models.CharField(max_length=100)


class UserLog(models.Model):
    xform_id = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    user_id = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    sync_token = models.CharField(max_length=COUCH_UUID_MAX_LEN)
    username = models.CharField(max_length=100)