from django.db import models

from dimagi.utils.decorators.memoized import memoized
from soil.util import get_task


class CaseUploadRecord(models.Model):
    domain = models.CharField(max_length=256)
    created = models.DateTimeField(auto_now_add=True)

    upload_id = models.UUIDField(unique=True)
    task_id = models.UUIDField(unique=True)
    couch_user_id = models.CharField(max_length=256)
    case_type = models.CharField(max_length=256)

    upload_file_meta = models.ForeignKey('CaseUploadFileMeta', null=True)

    @property
    @memoized
    def task(self):
        return get_task(self.task_id)

    def get_tempfile(self):
        from .filestorage import persistent_file_store
        return persistent_file_store.get_tempfile(self.upload_file_meta.identifier)


class CaseUploadFileMeta(models.Model):
    identifier = models.CharField(max_length=256, unique=True)
    filename = models.CharField(max_length=256)
    length = models.IntegerField()
