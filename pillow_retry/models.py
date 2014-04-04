import traceback
from datetime import datetime, timedelta
from django.conf import settings
import math
from django.db import models
from django.db.models.aggregates import Count


def _get_extra_args(limit, reduce, skip):
        extra_args = dict()
        if not reduce and limit is not None:
                extra_args.update(
                    limit=limit,
                    skip=skip
                )
        return extra_args

def name_path_from_object(obj):
        name = obj.__class__.__name__
        path = "{0}.{1}".format(obj.__class__.__module__, name)
        return name, path


class PillowError(models.Model):
    doc_id = models.CharField(max_length=255, null=False, db_index=True)
    pillow = models.CharField(max_length=255, null=False)
    date_created = models.DateTimeField()
    date_last_attempt = models.DateTimeField()
    date_next_attempt = models.DateTimeField(db_index=True, null=True)
    total_attempts = models.IntegerField(default=0)
    current_attempt = models.IntegerField(default=0, db_index=True)
    error_message = models.CharField(max_length=255, null=True)
    error_type = models.TextField(max_length=255, null=True)
    error_traceback = models.TextField(null=True)

    def add_attempt(self, exception, traceb, date=None):
        self.current_attempt += 1
        self.total_attempts += 1
        self.date_last_attempt = date or datetime.utcnow()
        self.error_message = exception.message
        self.error_type = name_path_from_object(exception)[1]
        self.error_traceback = "".join(traceback.format_tb(traceb))

        if self.current_attempt <= settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS:
            time_till_next = settings.PILLOW_RETRY_REPROCESS_INTERVAL * math.pow(self.current_attempt, settings.PILLOW_RETRY_BACKOFF_FACTOR)
            self.date_next_attempt = self.date_last_attempt + timedelta(minutes=time_till_next)
        else:
            self.date_next_attempt = None

    def reset_attempts(self):
        self.current_attempt = 0
        self.date_next_attempt = datetime.utcnow()

    @classmethod
    def get_or_create(cls, change, pillow):
        pillow_name, pillow_path = name_path_from_object(pillow)

        doc_id = change['id']
        try:
            error = cls.objects.get(doc_id=doc_id)
        except cls.DoesNotExist:
            error = None

        if not error:
            now = datetime.utcnow()
            error = PillowError(
                doc_id=doc_id,
                pillow=pillow_path,
                date_created=now,
                date_last_attempt=now,
                date_next_attempt=now,
            )

        return error

    @classmethod
    def get_errors_to_process(cls, utcnow, limit=None, skip=0, fetch_full=False):
        query = PillowError.objects \
            .filter(date_next_attempt__lte=utcnow) \
            .filter(current_attempt__lte=settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS)

        if not fetch_full:
            query = query.values('id', 'date_next_attempt')
        if limit is not None:
            return query[skip:skip+limit]
        else:
            return query

    @classmethod
    def get_pillows(cls):
        results = PillowError.objects.values('pillow').annotate(count=Count('pillow'))
        return (p['pillow'] for p in results)

    @classmethod
    def get_error_types(cls):
        results = PillowError.objects.values('error_type').annotate(count=Count('error_type'))
        return (e['error_type'] for e in results)
