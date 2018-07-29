from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import models


class BlobMigrationState(models.Model):
    slug = models.CharField(max_length=20, unique=True)
    timestamp = models.DateTimeField(auto_now=True)


class BlobExpiration(models.Model):
    '''
    This models records when temporary blobs should be deleted
    '''
    bucket = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, db_index=True)
    expires_on = models.DateTimeField(db_index=True)
    created_on = models.DateTimeField(auto_now=True)
    length = models.IntegerField()

    # This is set to True when the blob associated has been successfully deleted
    deleted = models.BooleanField(default=False, db_index=True)
