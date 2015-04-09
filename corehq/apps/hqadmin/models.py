from dimagi.ext.couchdbkit import *
from corehq.util.dates import datetime_to_iso_string


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
            startkey=[environment, datetime_to_iso_string(startdate)],
            endkey=[environment, datetime_to_iso_string(enddate)],
            reduce=False,
            limit=limit,
            include_docs=False
        ).all()
