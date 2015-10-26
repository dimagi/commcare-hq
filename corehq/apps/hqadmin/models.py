from django.db import models

from dimagi.ext.couchdbkit import *
from dimagi.utils.parsing import json_format_datetime
from pillowtop.utils import get_pillow_by_name
from pillowtop.exceptions import PillowNotFoundError


class HqDeploy(Document):
    date = DateTimeProperty()
    user = StringProperty()
    environment = StringProperty()
    code_snapshot = DictProperty()

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


class PillowCheckpointSeqStore(models.Model):
    seq = models.TextField()
    checkpoint_id = models.CharField(max_length=255, db_index=True)
    date_updated = models.DateTimeField(auto_now=True)

    @classmethod
    def get_by_pillow_name(cls, pillow_name):
        try:
            pillow = get_pillow_by_name(pillow_name)
        except PillowNotFoundError:
            # Could not find the pillow
            return None

        if not pillow:
            return None

        try:
            store = cls.objects.get(checkpoint_id=pillow.get_checkpoint()['_id'])
        except cls.DoesNotExist:
            return None

        return store
