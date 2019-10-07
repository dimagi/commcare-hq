import json
import traceback
from datetime import datetime, timedelta
from dateutil.parser import parse
from django.conf import settings
import math
from django.db import models
from django.db.models.aggregates import Count
from jsonfield.fields import JSONField

from pillow_retry import const
from pillowtop.feed.couch import change_from_couch_row
from pillowtop.feed.interface import ChangeMeta

ERROR_MESSAGE_LENGTH = 512


def _get_extra_args(limit, reduce, skip):
    extra_args = dict()
    if not reduce and limit is not None:
            extra_args.update(
                limit=limit,
                skip=skip
            )
    return extra_args


def path_from_object(obj):
    path = "{0}.{1}".format(obj.__class__.__module__, obj.__class__.__name__)
    return path


class PillowError(models.Model):
    doc_id = models.CharField(max_length=255, null=False)
    pillow = models.CharField(max_length=255, null=False, db_index=True)
    date_created = models.DateTimeField()
    date_last_attempt = models.DateTimeField()
    date_next_attempt = models.DateTimeField(db_index=True, null=True)
    total_attempts = models.IntegerField(default=0)
    current_attempt = models.IntegerField(default=0, db_index=True)
    error_type = models.CharField(max_length=255, null=True, db_index=True)
    error_traceback = models.TextField(null=True)
    change = JSONField(null=True)
    change_metadata = JSONField(null=True)

    @property
    def change_object(self):
        change = change_from_couch_row(self.change if self.change else {'id': self.doc_id})
        if self.change_metadata:
            change.metadata = ChangeMeta.wrap(self.change_metadata)
        change.document = None
        return change

    class Meta(object):
        app_label = 'pillow_retry'
        unique_together = ('doc_id', 'pillow',)

    def add_attempt(self, exception, traceb, change_meta=None, date=None):
        new_attempts = change_meta.attempts if change_meta else 1

        self.current_attempt += new_attempts
        self.total_attempts += new_attempts
        self.date_last_attempt = date or datetime.utcnow()
        self.error_type = path_from_object(exception)

        self.error_traceback = "{}\n\n{}".format(exception, "".join(traceback.format_tb(traceb)))

        if self.current_attempt <= const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS:
            time_till_next = const.PILLOW_RETRY_REPROCESS_INTERVAL * math.pow(self.current_attempt, 2)
            self.date_next_attempt = self.date_last_attempt + timedelta(minutes=time_till_next)
        else:
            self.date_next_attempt = None

    def reset_attempts(self):
        self.current_attempt = 0
        self.date_next_attempt = datetime.utcnow()

    def has_next_attempt(self):
        return self.current_attempt == 0 or (
            self.total_attempts <= const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF and
            self.current_attempt <= const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS
        )

    @classmethod
    def get_or_create(cls, change, pillow):
        change.document = None
        doc_id = change.id
        try:
            error = cls.objects.get(doc_id=doc_id, pillow=pillow.pillow_id)
        except cls.DoesNotExist:
            now = datetime.utcnow()
            error = PillowError(
                doc_id=doc_id,
                pillow=pillow.pillow_id,
                date_created=now,
                date_last_attempt=now,
                date_next_attempt=now,
                change=change.to_dict()
            )

            if change.metadata:
                error.date_created = change.metadata.publish_timestamp
                error.change_metadata = change.metadata.to_json()

        return error

    @classmethod
    def get_errors_to_process(cls, utcnow, limit=None, skip=0):
        """
        Get errors according the following rules:

            date_next_attempt <= utcnow
            AND
            (
                total_attempts <= multi_attempt_cutoff & current_attempt <= max_attempts
                OR
                total_attempts > multi_attempt_cutoff & current_attempt 0
            )

        where:
        * multi_attempt_cutoff = const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS * 3
        * max_attempts = const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS

        :param utcnow:      The current date and time in UTC.
        :param limit:       Paging limit param.
        :param skip:        Paging skip param.
        """
        max_attempts = const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS
        multi_attempts_cutoff = const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF
        query = PillowError.objects \
            .filter(date_next_attempt__lte=utcnow) \
            .filter(
                models.Q(current_attempt=0) |
                (models.Q(total_attempts__lte=multi_attempts_cutoff) & models.Q(current_attempt__lte=max_attempts))
            )

        # temporarily disable queuing of ConfigurableReportKafkaPillow errors
        query = query.filter(~models.Q(pillow='corehq.apps.userreports.pillow.ConfigurableReportKafkaPillow'))

        if limit is not None:
            return query[skip:skip+limit]
        else:
            return query

    @classmethod
    def bulk_reset_attempts(cls, last_attempt_lt, attempts_gte=None):
        if attempts_gte is None:
            attempts_gte = const.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS

        multi_attempts_cutoff = const.PILLOW_RETRY_MULTI_ATTEMPTS_CUTOFF
        return PillowError.objects.filter(
            models.Q(date_last_attempt__lt=last_attempt_lt),
            models.Q(current_attempt__gte=attempts_gte) | models.Q(total_attempts__gte=multi_attempts_cutoff)
        ).update(
            current_attempt=0,
            date_next_attempt=datetime.utcnow()
        )
