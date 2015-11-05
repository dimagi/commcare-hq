import os
import collections

from lxml import etree

from django.conf import settings
from django.db import models
from dimagi.utils.couch import RedisLockableMixIn
from couchforms.signals import xform_archived, xform_unarchived

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
    is_archived = models.BooleanField(default=False)
    is_duplicate = models.BooleanField(default=False)
    is_error = models.BooleanField(default=False)
    is_deprecated = models.BooleanField(default=False)
    is_submission_error_log = models.BooleanField(default=False)

    @classmethod
    def get(cls, id):
        try:
            return XFormInstanceSQL.objects.get(form_uuid=id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @property
    def form_id(self):
        return self.form_uuid

    @property
    def is_normal(self):
        return not (self.is_error or self.is_deprecated or self.is_duplicate or self.is_archived)

    @property
    def form_data(self):
        from .utils import convert_xform_to_json
        xml = self._get_xml()
        return convert_xform_to_json(xml)

    @property
    def history(self):
        return self.xformoperationsql_set.order_by('date')

    def get_xml_element(self):
        xml = self._get_xml()
        if not xml:
            return None

        def _to_xml_element(payload):
            if isinstance(payload, unicode):
                payload = payload.encode('utf-8', errors='replace')
            return etree.fromstring(payload)
        return _to_xml_element(xml)

    def _get_xml(self):
        xform_attachment = self.xformattachmentsql_set.filter(name='form.xml').first()
        return xform_attachment.read_content()

    def archive(self, user=None):
        if self.is_archived:
            return
        self.is_archived = True
        self.xformoperationsql_set.create(
            user=user,
            operation=XFormOperationSQL.ARCHIVE,
        )
        self.save()
        xform_archived.send(sender="form_processor", xform=self)

    def unarchive(self, user=None):
        if not self.is_archived:
            return
        self.is_archived = False
        self.xformoperationsql_set.create(
            user=user,
            operation=XFormOperationSQL.UNARCHIVE,
        )
        self.save()
        # xform_unarchived.send(sender="form_processor", xform=self)


class XFormAttachmentSQL(models.Model):
    attachment_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    xform = models.ForeignKey(XFormInstanceSQL, to_field='form_uuid')
    name = models.CharField(max_length=255, db_index=True)
    content_type = models.CharField(max_length=255)
    md5 = models.CharField(max_length=255)

    @property
    def filepath(self):
        if getattr(settings, 'IS_TRAVIS', False):
            return os.path.join('/home/travis/', self.attachment_uuid)
        return os.path.join('/tmp/', self.attachment_uuid)

    def write_content(self, content):
        with open(self.filepath, 'w+') as f:
            f.write(content)

    def read_content(self):
        with open(self.filepath, 'r+') as f:
            content = f.read()
        return content


class XFormOperationSQL(models.Model):
    ARCHIVE = 'archive'
    UNARCHIVE = 'unarchive'

    user = models.CharField(max_length=255, null=True)
    operation = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    xform = models.ForeignKey(XFormInstanceSQL, to_field='form_uuid')


Attachment = collections.namedtuple('Attachment', 'name content content_type')
