from django.db import models


class TaskRecord(models.Model):
    """
    Record to track a celery task/message prior to being processed by a worker.
    Once processed by a worker, whether it fails or succeeds, this record is deleted.
    """
    task_id = models.UUIDField(null=True)
    name = models.CharField(max_length=255)
    args = models.JSONField()
    kwargs = models.JSONField()
    sent = models.BooleanField()  # if True, task was successfully sent to the broker
    error = models.TextField(blank=True, default='')  # optional - captures issues queueing task
    date_created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task_id"], condition=models.Q(task_id__isnull=False), name="unique_nonnull_task_id"
            )
        ]

    def __str__(self):
        return f"<{self.name}> {self.task_id} {self.date_created}"
