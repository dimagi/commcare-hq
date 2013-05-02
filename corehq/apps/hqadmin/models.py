from couchdbkit.ext.django.schema import *


class HqDeploy(Document):
    date = DateTimeProperty()
    user = StringProperty()

    @classmethod
    def get_latest(cls):
        return HqDeploy.view('hqadmin/deploy_history', reduce=False, limit=1, descending=True).one()