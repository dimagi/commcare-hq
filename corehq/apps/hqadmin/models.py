from django.db import models

from dimagi.ext.couchdbkit import *
from dimagi.utils.parsing import json_format_datetime


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
