from django.db import models


class MigrationCheckpoint(models.Model):
    domain = models.CharField(max_length=100)
    date = models.DateTimeField(null=True)
    start_date = models.DateTimeField(null=True)
    api = models.CharField(max_length=100)
    limit = models.PositiveIntegerField()
    offset = models.PositiveIntegerField()
