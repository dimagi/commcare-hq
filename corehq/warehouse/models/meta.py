from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import models


class Batch(models.Model):
    batch_id = models.UUIDField(unique=True, db_index=True, primary_key=True)

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    created_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True)


class CommitRecord(models.Model):
    '''
    A CommitRecord records meta data about a certain warehouse table's
    batch.
    '''
    batch = models.ForeignKey('Batch', on_delete=models.PROTECT)

    slug = models.CharField(max_length=100)
    error = models.TextField()
    success = models.NullBooleanField()
    verified = models.NullBooleanField()

    created_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True)
