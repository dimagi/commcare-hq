from django.db import models


class BlobMigrationState(models.Model):
    slug = models.CharField(max_length=20, unique=True)
    timestamp = models.DateTimeField(auto_now=True)
