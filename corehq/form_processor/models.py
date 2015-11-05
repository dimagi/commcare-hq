import os
import collections
from json_field.fields import JSONField

from lxml import etree

from django.conf import settings
from django.db import models
from dimagi.utils.couch import RedisLockableMixIn

from .abstract_models import AbstractXFormInstance, AbstractCommCareCase
from .exceptions import XFormNotFound


Attachment = collections.namedtuple('Attachment', 'name content content_type')


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
            return os.path.join('/home/travis/', self.attachment_uuid)
        return os.path.join('/tmp/', self.attachment_uuid)

    def write_content(self, content):
        with open(self.filepath, 'w+') as f:
            f.write(content)

    def read_content(self):
        with open(self.filepath, 'r+') as f:
            content = f.read()
        return content


class CommCareCaseSQL(models.Model, AbstractCommCareCase):
    case_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    domain = models.CharField(max_length=255)
    case_type = models.CharField(max_length=255)

    owner_id = models.CharField(max_length=255)

    opened_on = models.DateTimeField(null=False)
    opened_by = models.CharField(max_length=255, null=False)

    modified_on = models.DateTimeField(null=False)
    server_modified_on = models.DateTimeField(null=False)
    modified_by = models.CharField(max_length=255)

    closed = models.BooleanField(default=False, null=False)
    closed_on = models.DateTimeField(null=True)
    closed_by = models.CharField(max_length=255, null=False)

    deleted = models.BooleanField(default=False, null=False)

    external_id = models.CharField(max_length=255)

    case_json = JSONField(lazy=True)
    attachments_json = JSONField(lazy=True)

    @property
    def case_id(self):
        return self.case_uuid

    def hard_delete(self):
        self.delete()

    def soft_delete(self):
        self.deleted = True
        self.save()

    def is_deleted(self):
        return self.deleted

    def get_attachment(self, attachment_name):
        assert attachment_name in self.attachments_json
        with open(self._get_attachment_path(attachment_name), 'r+') as f:
            content = f.read()
        return content

    def _get_attachment_path(self, attachment_name):
        attachment_id = '{}_{}'.format(self.case_uuid, attachment_name)
        if getattr(settings, 'IS_TRAVIS', False):
            return os.path.join('/home/travis/', attachment_id)
        return os.path.join('/tmp/', attachment_id)

    @classmethod
    def get(cls, case_id):
        return CommCareCaseSQL.objects.get(case_uuid=case_id)

    @classmethod
    def get_cases(cls, ids):
        return CommCareCaseSQL.objects.filter(case_uuid__in=list(ids))

    @classmethod
    def get_case_xform_ids(cls, case_id):
        return CaseForms.objects.filter(case_uuid=case_id)

    def __unicode__(self):
        return (
            "CommCareCase("
                "case_id='{c.case_uuid}', "
                "domain='{c.domain}', "
                "closed={c.closed}, "
                "owner_id='{c.owner_id}', "
                "server_modified_on='{c.server_modified_on}')"
        ).format(c=self)

    class Meta:
        # TODO SK 2015-11-05: verify that these are the indexes we want
        # also consider partial indexes
        index_together = [
            ["domain", "owner_id"],
            ["domain", "closed", "server_modified_on"],
        ]


class CommCareCaseIndexSQL(models.Model):
    CHILD = 0
    EXTENSION = 1
    RELATIONSHIP_CHOICES = (
        (CHILD, 'child'),
        (EXTENSION, 'extension'),
    )

    case = models.ForeignKey('CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=True)
    domain = models.CharField(max_length=255)  # TODO SK 2015-11-05: is this necessary or should we join on case?
    identifier = models.CharField(max_length=255, null=False)
    referenced_id = models.CharField(max_length=255, null=False)
    referenced_type = models.CharField(max_length=255, null=False)
    relationship = models.PositiveSmallIntegerField(choices=RELATIONSHIP_CHOICES)

    def __unicode__(self):
        return (
            "CaseIndex("
                "case_id='{i.case_uuid}', "
                "domain='{i.domain}', "
                "identifier='{i.identifier}', "
                "referenced_type='{i.referenced_type}', "
                "referenced_id='{i.referenced_id}', "
                "relationship='{i.relationship})"
        ).format(i=self)

    class Meta:
        index_together = [
            ["domain", "referenced_id"],
        ]


class CaseForms(models.Model):
    case = models.ForeignKey('CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=False)
    form_uuid = models.CharField(max_length=255, null=False)  # can't be a foreign key due to partitioning

    class Meta:
        unique_together = ("case", "form_uuid")
