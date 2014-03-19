from couchdbkit.ext.django.schema import *


class HqDeploy(Document):
    date = DateTimeProperty()
    user = StringProperty()
    environment = StringProperty()
    code_snapshot = DictProperty()

    @classmethod
    def get_latest(cls, environment):
        return HqDeploy.view(
            'hqadmin/deploy_history',
            startkey=[environment, {}],
            endkey=[environment],
            reduce=False,
            limit=1,
            descending=True,
            include_docs=True
        ).one()

    @classmethod
    def get_list(cls, environment, startdate, enddate, limit=50):
        return HqDeploy.view(
            'hqadmin/deploy_history',
            startkey=[environment, startdate.strftime("%Y-%m-%dT%H:%M:%SZ")],
            endkey=[environment, enddate.strftime("%Y-%m-%dT%H:%M:%SZ")],
            reduce=False,
            limit=limit,
            include_docs=False
        ).all()