from django.db import models


class TaskRecord(models.Model):
    task_id = models.UUIDField(null=True)
    name = models.CharField(max_length=255)
    args = models.JSONField()
    kwargs = models.JSONField()
    sent = models.BooleanField()  # if True, task was successfully sent to the broker
    date_created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task_id"], condition=models.Q(task_id__isnull=False), name="unique_nonnull_task_id"
            )
        ]
