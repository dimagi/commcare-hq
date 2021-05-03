from django.db import models
from django.contrib.postgres.fields import JSONField


class BulkActionsConfig(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    action_type = models.CharField(max_length=10)
    mapping = JSONField(null=True)
    form = models.UUIDField(null=True)
