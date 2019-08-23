from datetime import date

from django.db import models

from dimagi.ext.couchdbkit import *
from dimagi.utils.parsing import json_format_datetime
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_pillow_by_name, get_all_pillow_instances, safe_force_seq_int


class HqDeploy(Document):
    date = DateTimeProperty()
    user = StringProperty()
    environment = StringProperty()
    code_snapshot = DictProperty()
    diff_url = StringProperty()

    @classmethod
    def get_latest(cls, environment, limit=1):
        result = HqDeploy.view(
            'hqadmin/deploy_history',
            startkey=[environment, {}],
            endkey=[environment],
            reduce=False,
            limit=limit,
            descending=True,
            include_docs=True
        )
        return result.all()

    @classmethod
    def get_list(cls, environment, startdate, enddate, limit=50):
        return HqDeploy.view(
            'hqadmin/deploy_history',
            startkey=[environment, json_format_datetime(startdate)],
            endkey=[environment, json_format_datetime(enddate)],
            reduce=False,
            limit=limit,
            include_docs=False
        ).all()


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
