from django.db import models


class TaskRecordState(models.TextChoices):
    # the following are meant to replicate celery task states
    # https://docs.celeryq.dev/en/latest/reference/celery.states.html
    FAILURE = "FAILURE", "Failure"
    PENDING = "PENDING", "Pending"  # task was created, but not yet sent to the broker
    RECEIVED = "RECEIVED", "Received"  # task was received by a worker, not a broker
    REJECTED = "REJECTED", "Rejected"  # not in docs, but set when task cannot be processed by worker
    RETRY = "RETRY", "Retry"
    REVOKED = "REVOKED", "Revoked"
    SENT = "SENT", "Sent"  # commcare adds this state in a receiver for the after_task_publish signal
    STARTED = "STARTED", "Started"
    SUCCESS = "SUCCESS", "Success"


class TaskRecord(models.Model):
    task_id = models.UUIDField(null=True)
    name = models.CharField(max_length=255)
    args = models.JSONField()
    kwargs = models.JSONField()
    state = models.CharField(choices=TaskRecordState.choices, default=TaskRecordState.PENDING)
    date_created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task_id"], condition=models.Q(task_id__isnull=False), name="unique_nonnull_task_id"
            )
        ]
