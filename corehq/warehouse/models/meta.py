from django.db import models


class BatchRecord(models.Model):
    batch_id = models.UUIDField(unique=True, db_index=True, primary_key=True)

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    created_on = models.DateTimeField(auto_now_add=True)


class CommitRecord(models.Model):
    '''
    A CommitRecord records meta data about a certain warehouse table's
    batch.
    '''
    batch_record = models.ForeignKey('BatchRecord', on_delete=models.PROTECT)

    slug = models.CharField(max_length=100)
    error = models.TextField()
    success = models.NullBooleanField()
    verified = models.NullBooleanField()

    created_on = models.DateTimeField(auto_now_add=True)
