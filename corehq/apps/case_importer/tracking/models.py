from django.db import models
from jsonfield import JSONField
from corehq.apps.case_importer.tracking.task_status import TaskStatus, \
    get_task_status_json

from dimagi.utils.decorators.memoized import memoized
from soil.util import get_task

MAX_COMMENT_LENGTH = 2048


class CaseUploadRecord(models.Model):
    domain = models.CharField(max_length=256)
    created = models.DateTimeField(auto_now_add=True)

    upload_id = models.UUIDField(unique=True)
    task_id = models.UUIDField(unique=True)
    task_status_json = JSONField(null=True)
    couch_user_id = models.CharField(max_length=256)
    case_type = models.CharField(max_length=256)
    comment = models.TextField(null=True)

    upload_file_meta = models.ForeignKey('CaseUploadFileMeta', null=True)

    class Meta(object):
        index_together = ('domain', 'created')

    @property
    @memoized
    def task(self):
        return get_task(self.task_id)

    @memoized
    def get_task_status_json(self):
        if self.task_status_json:
            return TaskStatus.wrap(self.task_status_json)
        else:
            return get_task_status_json(str(self.task_id))

    def set_task_status_json_if_finished(self):
        """
        set task_status_json based on self.task_id

        :return: True if the caller must save model to persist the effect

        """
        if self.task_status_json is None:
            # intentionally routing through method to prime local cache
            task_status_json = self.get_task_status_json()
            if task_status_json.is_finished():
                self.task_status_json = task_status_json
                return True

        return False

    def get_tempfile_ref_for_upload_ref(self):
        from .filestorage import persistent_file_store
        return persistent_file_store.get_tempfile_ref_for_contents(self.upload_file_meta.identifier)


class CaseUploadFileMeta(models.Model):
    identifier = models.CharField(max_length=256, unique=True)
    filename = models.CharField(max_length=256)
    length = models.IntegerField()


class CaseUploadFormRecord(models.Model):
    case_upload_record = models.ForeignKey(CaseUploadRecord, related_name='form_records')
    form_id = models.CharField(max_length=256, unique=True)
