from django.db import models


class DocTypeMigrationState(models.Model):
    slug = models.CharField(max_length=20, unique=True)
    original_seq = models.TextField()
