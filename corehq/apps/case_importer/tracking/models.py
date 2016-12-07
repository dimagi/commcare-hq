from django.db import models
from dimagi.ext import jsonobject
from dimagi.utils.decorators.memoized import memoized
from soil.util import get_task


class CaseUploadRecord(models.Model):
    domain = models.CharField(max_length=256)
    created = models.DateTimeField(auto_now_add=True)

    upload_id = models.UUIDField(unique=True)
    task_id = models.UUIDField(unique=True)
    couch_user_id = models.CharField(max_length=256)
    case_type = models.CharField(max_length=256)

    @property
    @memoized
    def task(self):
        return get_task(self.task_id)


class CaseUploadJSON(jsonobject.JsonObject):
    _allow_dynamic_properties = False

    domain = jsonobject.StringProperty(required=True)
    created = jsonobject.DateTimeProperty(required=True)
    upload_id = jsonobject.StringProperty(required=True)
    task_id = jsonobject.StringProperty(required=True)
    couch_user_id = jsonobject.StringProperty(required=True)
    case_type = jsonobject.StringProperty(required=True)

    @classmethod
    def from_model(cls, other):
        return cls(
            domain=other.domain,
            created=other.created,
            upload_id=unicode(other.upload_id),
            task_id=unicode(other.task_id),
            couch_user_id=other.couch_user_id,
            case_type=other.case_type,
        )
