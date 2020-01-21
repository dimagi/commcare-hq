from datetime import date, datetime

from django.db import DEFAULT_DB_ALIAS, models

from dimagi.ext.couchdbkit import *
from dimagi.utils.parsing import json_format_datetime
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import (
    get_all_pillow_instances,
    get_pillow_by_name,
    safe_force_seq_int,
)


class SQLHqDeploy(models.Model):
    date = models.DateTimeField(default=datetime.utcnow, db_index=True)
    user = models.CharField(max_length=100)
    environment = models.CharField(max_length=100)
    diff_url = models.CharField(max_length=126, null=True)
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta(object):
        db_table = "hqadmin_hqdeploy"

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        # Update or create couch doc
        if self.couch_id:
            doc = HqDeploy.wrap(HqDeploy.get_db().get(self.couch_id))
        else:
            doc = HqDeploy(
                date=self.date,
                user=self.user,
                environment=self.environment,
                diff_url=self.diff_url,
            )

        doc.save(from_sql=True)
        self.couch_id = doc.get_id

        # Save to SQL
        super().save(
            force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields
        )

    @classmethod
    def get_latest(cls, environment, limit=1):
        query = SQLHqDeploy.objects.filter(environment=environment).order_by("-date")
        if limit:
            return query[:limit]
        return query


class HqDeploy(Document):
    date = DateTimeProperty()
    user = StringProperty()
    environment = StringProperty()
    code_snapshot = DictProperty()
    diff_url = StringProperty()

    def save(self, *args, **kwargs):
        # Save to couch
        # This must happen first so the SQL save finds this doc and doesn't recreate it
        super().save(*args, **kwargs)

        # Save to SQL
        if not kwargs.pop('from_sql', False):
            model, created = SQLHqDeploy.objects.update_or_create(
                couch_id=self.get_id,
                defaults={
                    'date': self.date,
                    'user': self.user,
                    'environment': self.environment,
                    'diff_url': self.diff_url,
                }
            )


class HistoricalPillowCheckpoint(models.Model):
    seq = models.TextField()
    seq_int = models.IntegerField(null=True)
    checkpoint_id = models.CharField(max_length=255, db_index=True)
    date_updated = models.DateField()

    @classmethod
    def create_pillow_checkpoint_snapshots(cls):
        for pillow in get_all_pillow_instances():
            cls.create_checkpoint_snapshot(pillow.checkpoint)

    @classmethod
    def create_checkpoint_snapshot(cls, checkpoint):
        db_seq = checkpoint.get_current_sequence_id()
        cls.objects.create(seq=db_seq,
                           seq_int=safe_force_seq_int(db_seq),
                           checkpoint_id=checkpoint.checkpoint_id,
                           date_updated=date.today())

    @classmethod
    def get_latest_for_pillow(cls, pillow_name):
        try:
            pillow = get_pillow_by_name(pillow_name)
        except PillowNotFoundError:
            # Could not find the pillow
            return None

        if not pillow:
            return None

        return cls.get_latest(pillow.checkpoint.checkpoint_id)

    @classmethod
    def get_latest(cls, checkpoint_id):
        try:
            return cls.objects.filter(checkpoint_id=checkpoint_id)[0]
        except IndexError:
            return None

    @classmethod
    def get_historical_max(cls, checkpoint_id):
        try:
            return cls.objects.filter(checkpoint_id=checkpoint_id).order_by('-seq_int')[0]
        except IndexError:
            return None

    class Meta(object):
        ordering = ['-date_updated']
