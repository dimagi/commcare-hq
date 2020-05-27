import json

from collections import defaultdict

from datetime import date, datetime

from django.db import DEFAULT_DB_ALIAS, models

from dimagi.ext.couchdbkit import *
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import (
    get_all_pillow_instances,
    get_pillow_by_name,
    safe_force_seq_int,
)


class HqDeploy(models.Model):
    date = models.DateTimeField(default=datetime.utcnow, db_index=True)
    user = models.CharField(max_length=100)
    environment = models.CharField(max_length=100, null=True)
    diff_url = models.CharField(max_length=255, null=True)

    class Meta():
        ordering = ["-date"]


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
    def get_historical_max(cls, checkpoint_id, by_partition=False):
        if by_partition:
            # limit to last 10 days
            checkpoints = cls.objects.filter(checkpoint_id=checkpoint_id)[:10]
            max_offsets = defaultdict(int)
            for checkpoint in checkpoints:
                offset_info = json.loads(checkpoint.seq)
                for partition, offset in offset_info.items():
                    if offset > max_offsets[partition]:
                        max_offsets[partition] = offset
            return max_offsets
        else:
            try:
                return cls.objects.filter(checkpoint_id=checkpoint_id).order_by('-seq_int')[0]
            except IndexError:
                return None


    class Meta(object):
        ordering = ['-date_updated']
