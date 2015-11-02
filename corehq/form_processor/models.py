from django.db import models
from dimagi.utils.couch import RedisLockableMixIn

from .abstract_models import AbstractXFormInstance
from .exceptions import XFormNotFound


class XFormInstanceSQL(models.Model, AbstractXFormInstance, RedisLockableMixIn):
    """An XForms SQL instance."""
    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255)
    form_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    form_data = models.TextField(null=True)
    received_on = models.DateTimeField(auto_now_add=True)

    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    partial_submission = models.BooleanField(default=False)
    # history = SchemaListProperty(XFormOperation)
    # auth_context = DictProperty()
    submit_ip = models.CharField(max_length=255, null=True)
    #openrosa_headers = DictProperty()
    last_sync_token = models.CharField(max_length=255, null=True)
    # almost always a datetime, but if it's not parseable it'll be a string
    #date_header = DefaultProperty()
    date_header = models.DateTimeField(null=True)
    build_id = models.CharField(max_length=255, null=True)
    #export_tag = DefaultProperty(name='#export_tag')


    @classmethod
    def get(cls, id):
        try:
            return XFormInstanceSQL.objects.get(form_uuid=id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @property
    def form_id(self):
        return self.form_uuid
