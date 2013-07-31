from couchdbkit.ext.django.schema import *


class HqDeploy(Document):
    date = DateTimeProperty()
    user = StringProperty()
    environment = StringProperty()
    code_snapshot = DictProperty()

    @classmethod
    def get_latest(cls,  environment):
        return HqDeploy.view('hqadmin/deploy_history', startkey=[environment, {}], endkey=[environment], reduce=False, limit=1, descending=True, include_docs=True).one()