import uuid

from django.db import models


class TaskRecord(models.Model):
    """
    Record to track a celery task/message prior to being processed by a worker.
    Once processed by a worker, whether it fails or succeeds, this record is deleted.
    """

    task_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    args = models.JSONField()
    kwargs = models.JSONField()
    error = models.TextField(blank=True, default='')  # optional - captures issues queueing task
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"<{self.name}> {self.task_id} {self.date_created}"
