import os
import collections

from lxml import etree

from django.conf import settings
from django.db import models
from dimagi.utils.couch import RedisLockableMixIn

from .abstract_models import AbstractXFormInstance
from .exceptions import XFormNotFound


class XFormInstanceSQL(models.Model, AbstractXFormInstance, RedisLockableMixIn):
    """An XForms SQL instance."""
    form_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255)
    received_on = models.DateTimeField()

    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    partial_submission = models.BooleanField(default=False)
    # history = SchemaListProperty(XFormOperation)
    # auth_context = DictProperty()
    submit_ip = models.CharField(max_length=255, null=True)
    # openrosa_headers = DictProperty()
    last_sync_token = models.CharField(max_length=255, null=True)
    # almost always a datetime, but if it's not parseable it'll be a string
    date_header = models.DateTimeField(null=True)
    build_id = models.CharField(max_length=255, null=True)
    # export_tag = DefaultProperty(name='#export_tag')

    @classmethod
    def get(cls, id):
        try:
            return XFormInstanceSQL.objects.get(form_uuid=id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @property
    def form_id(self):
        return self.form_uuid

    def get_xml_element(self):
        xml = self._get_xml()
        if not xml:
            return None

        def _to_xml_element(payload):
            if isinstance(payload, unicode):
                payload = payload.encode('utf-8', errors='replace')
            return etree.fromstring(payload)
        return _to_xml_element(xml)

    @property
    def form_data(self):
        from .utils import convert_xform_to_json
        xml = self._get_xml()
        return convert_xform_to_json(xml)

    def _get_xml(self):
        xform_attachment = self.xformattachmentsql_set.filter(name='form.xml').first()
        return xform_attachment.read_content()


class XFormAttachmentSQL(models.Model):
    attachment_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    xform = models.ForeignKey(XFormInstanceSQL, to_field='form_uuid')
    name = models.CharField(max_length=255, db_index=True)
    content_type = models.CharField(max_length=255)
    md5 = models.CharField(max_length=255)

    @property
    def filepath(self):
        if getattr(settings, 'IS_TRAVIS', False):
            return os.path.join('/home/travis/tmp/', self.attachment_uuid)
        return os.path.join('/tmp/', self.attachment_uuid)

    def write_content(self, content):
        with open(self.filepath, 'w+') as f:
            f.write(content)

    def read_content(self):
        with open(self.filepath, 'r+') as f:
            content = f.read()
        return content

Attachment = collections.namedtuple('Attachment', 'name content content_type')
