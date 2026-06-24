import uuid

from django.db import models

from corehq.sql_db.fields import ModelClassField


class DeletedCouchDoc(models.Model):
    doc_id = models.CharField(max_length=126)
    doc_type = models.CharField(max_length=126)
    deleted_on = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['doc_id', 'doc_type'], name='deletedcouchdoc_unique_id_and_type')
        ]


class BulkDeletionJob(models.Model):
    """Tracks a job requested via the bulk deletion API."""

    class Status(models.TextChoices):
        PENDING = 'pending'
        RUNNING = 'running'
        COMPLETE = 'complete'
        FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=255, db_index=True)
    model = ModelClassField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_by = models.CharField(max_length=255)
    api_key = models.ForeignKey(
        'users.HQApiKey',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bulk_deletion_jobs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requested_ids_blob_key = models.CharField(max_length=64)
    skipped_ids_blob_key = models.CharField(max_length=64)
    processed_count = models.PositiveIntegerField(default=0)
    deleted_count = models.PositiveIntegerField(default=0)
