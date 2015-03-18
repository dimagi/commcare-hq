from django.db import models
from corehq.apps.locations.models import SQLLocation


class Checkpoint(models.Model):
    domain = models.CharField(max_length=100)
    date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    api = models.CharField(max_length=100)
    limit = models.PositiveIntegerField()
    offset = models.PositiveIntegerField()

    class Meta:
        abstract = True


class MigrationCheckpoint(Checkpoint):
    pass


class StockDataCheckpoint(Checkpoint):
    location = models.ForeignKey(SQLLocation, null=True, blank=True)
