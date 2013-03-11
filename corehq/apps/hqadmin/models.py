from couchdbkit.ext.django.schema import *


class HqDeploy(Document):
    date = DateTimeProperty()