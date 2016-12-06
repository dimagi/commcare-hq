from django.db import models
from dimagi.ext import jsonobject


class CaseUploadRecord(models.Model):
    domain = models.CharField(max_length=256)
    created = models.DateTimeField(auto_now_add=True)

    upload_id = models.UUIDField()
    task_id = models.UUIDField()


class CaseUploadJSON(jsonobject.JsonObject):
    _allow_dynamic_properties = False

    domain = jsonobject.StringProperty(required=True)
    created = jsonobject.DateTimeProperty(required=True)
    upload_id = jsonobject.StringProperty(required=True)
    task_id = jsonobject.StringProperty(required=True)

    @classmethod
    def from_model(cls, other):
        return cls(
            domain=other.domain,
            created=other.created,
            upload_id=unicode(other.upload_id),
            task_id=unicode(other.task_id)
        )
