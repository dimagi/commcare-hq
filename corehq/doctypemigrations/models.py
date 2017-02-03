from django.db import models


class DocTypeMigration(models.Model):
    slug = models.CharField(max_length=20, unique=True)
    original_seq = models.TextField()
    cleanup_complete = models.BooleanField(default=False)


class DocTypeMigrationCheckpoint(models.Model):
    migration = models.ForeignKey(DocTypeMigration, on_delete=models.CASCADE)
    seq = models.TextField()
    timestamp = models.DateTimeField(auto_now=True)
