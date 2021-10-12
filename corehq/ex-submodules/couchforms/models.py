from django.db import models

from dimagi.ext.couchdbkit import DocumentSchema


class DefaultAuthContext(DocumentSchema):

    def is_valid(self):
        return True


class UnfinishedSubmissionStub(models.Model):
    id = models.BigAutoField(primary_key=True)
    xform_id = models.CharField(max_length=200)
    timestamp = models.DateTimeField(db_index=True)
    saved = models.BooleanField(default=False)
    domain = models.CharField(max_length=256)
    date_queued = models.DateTimeField(null=True, db_index=True)
    attempts = models.IntegerField(default=0)

    def __str__(self):
        return str(
            "UnfinishedSubmissionStub("
            "xform_id={s.xform_id},"
            "timestamp={s.timestamp},"
            "saved={s.saved},"
            "domain={s.domain})"
        ).format(s=self)

    class Meta(object):
        app_label = 'couchforms'
        indexes = (
            models.Index(fields=['xform_id']),
        )


class UnfinishedArchiveStub(models.Model):
    xform_id = models.CharField(max_length=200, unique=True)
    user_id = models.CharField(max_length=200, default=None, blank=True, null=True)
    timestamp = models.DateTimeField(db_index=True)
    archive = models.BooleanField(default=False)
    history_updated = models.BooleanField(default=False)
    domain = models.CharField(max_length=256)
    attempts = models.IntegerField(default=0)

    def __str__(self):
        return str(
            "UnfinishedArchiveStub("
            "xform_id={s.xform_id},"
            "user_id={s.user_id},"
            "timestamp={s.timestamp},"
            "archive={s.archive},"
            "history_updated={s.history_updated},"
            "domain={s.domain})"
        ).format(s=self)

    class Meta(object):
        app_label = 'couchforms'
