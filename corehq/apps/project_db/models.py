from django.db import models


class PendingOperation(models.Model):
    """An operation needed to bring a domain's ProjectDB up to date"""
    class Operation(models.TextChoices):
        SYNC = 'sync'
        BACKFILL = 'backfill'

    domain = models.CharField(max_length=255, db_index=True)
    operation = models.CharField(max_length=32, choices=Operation.choices)
    args = models.JSONField(default=dict)
    created_on = models.DateTimeField(auto_now_add=True)
