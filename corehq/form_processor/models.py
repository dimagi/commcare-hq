import os
import collections
import logging

from lxml import etree
from json_field.fields import JSONField
from jsonobject.api import re_date
from django.conf import settings
from django.db import models, transaction

from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.decorators.memoized import memoized
from dimagi.ext import jsonobject
from couchforms.signals import xform_archived, xform_unarchived
from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty
from corehq.util.dates import iso_string_to_datetime

from .abstract_models import AbstractXFormInstance, AbstractCommCareCase
from .exceptions import XFormNotFound


Attachment = collections.namedtuple('Attachment', 'name content content_type')


class XFormInstanceSQL(models.Model, AbstractXFormInstance, RedisLockableMixIn):
    """An XForms SQL instance."""
    NORMAL = 0
    ARCHIVED = 1
    DEPRECATED = 2
    DUPLICATE = 3
    ERROR = 4
    SUBMISSION_ERROR_LOG = 5
    STATES = (
        (NORMAL, 'normal'),
        (ARCHIVED, 'archived'),
        (DEPRECATED, 'deprecated'),
        (DUPLICATE, 'duplicate'),
        (ERROR, 'error'),
        (SUBMISSION_ERROR_LOG, 'submission_error'),
    )

    form_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255)

    # The time at which the server has received the form
    received_on = models.DateTimeField()

    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    auth_context = JSONField(lazy=True)
    openrosa_headers = JSONField(lazy=True)
    partial_submission = models.BooleanField(default=False)
    submit_ip = models.CharField(max_length=255, null=True)
    last_sync_token = models.CharField(max_length=255, null=True)
    # almost always a datetime, but if it's not parseable it'll be a string
    date_header = models.DateTimeField(null=True)
    build_id = models.CharField(max_length=255, null=True)
    # export_tag = DefaultProperty(name='#export_tag')
    state = models.PositiveSmallIntegerField(choices=STATES, default=NORMAL)

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
        return self.state == self.NORMAL

    @property
    def is_archived(self):
        return self.state == self.ARCHIVED

    @property
    def is_deprecated(self):
        return self.state == self.DEPRECATED

    @property
    def is_duplicate(self):
        return self.state == self.DUPLICATE

    @property
    def is_error(self):
        return self.state == self.ERROR

    @property
    def is_submission_error_log(self):
        return self.state == self.SUBMISSION_ERROR_LOG

    @property
    @memoized
    def form_data(self):
        from .utils import convert_xform_to_json
        xml = self._get_xml()
        return convert_xform_to_json(xml)

    @property
    def history(self):
        return self.xformoperationsql_set.order_by('date')

    @property
    def metadata(self):
        if const.TAG_META in self.form_data:
            return XFormMetadata.wrap(self._clean_metadata(self.form_data[const.TAG_META]))

        return None

    def _clean_metadata(self, meta_block):
        from .utils import get_text_attribute

        if not meta_block:
            return meta_block
        meta_block = self._remove_unused_meta_attributes(meta_block)
        meta_block['appVersion'] = get_text_attribute(meta_block.get('appVersion'))
        meta_block['location'] = get_text_attribute(meta_block.get('location'))
        meta_block = self._parse_meta_times(meta_block)

        # also clean dicts on the return value, since those are not allowed
        for key in meta_block:
            if isinstance(meta_block[key], dict):
                meta_block[key] = self._flatten_dict(meta_block[key])

        return meta_block

    def _flatten_dict(self, dictionary):
        return ", ".join("{}:{}".format(k, v) for k, v in dictionary.items())

    def _remove_unused_meta_attributes(self, meta_block):
        for key in meta_block.keys():
            # remove attributes from the meta block
            if key.startswith('@'):
                del meta_block[key]
        return meta_block

    def _parse_meta_times(self, meta_block):
        for key in ("timeStart", "timeEnd"):
            if meta_block.get(key, None):
                if re_date.match(meta_block[key]):
                    # this kind of leniency is pretty bad and making it midnight in UTC
                    # is totally arbitrary here for backwards compatibility
                    meta_block[key] += 'T00:00:00.000000Z'
                try:
                    # try to parse to ensure correctness
                    parsed = iso_string_to_datetime(meta_block[key])
                    # and set back in the right format in case it was a date, not a datetime
                    meta_block[key] = json_format_datetime(parsed)
                except Exception:
                    logging.exception('Could not parse meta_block')
                    # we couldn't parse it
                    del meta_block[key]
            else:
                # it was empty, also a failure
                del meta_block[key]

        return meta_block

    def to_json(self):
        from .serializers import XFormInstanceSQLSerializer
        serializer = XFormInstanceSQLSerializer(self)
        return serializer.data

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
        with transaction.atomic():
            self.state = self.ARCHIVED
            self.xformoperationsql_set.create(
                user=user,
                operation=XFormOperationSQL.ARCHIVE,
            )
            self.save()
        xform_archived.send(sender="form_processor", xform=self)

    def unarchive(self, user=None):
        if not self.is_archived:
            return
        with transaction.atomic():
            self.state = self.NORMAL
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


class XFormMetadata(jsonobject.JsonObject):
    """
    Metadata of an xform, from a meta block structured like:

        <Meta>
            <timeStart />
            <timeEnd />
            <instanceID />
            <userID />
            <deviceID />
            <deprecatedID />
            <username />

            <!-- CommCare extension -->
            <appVersion />
            <location />
        </Meta>

    See spec: https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaMetaDataSchema

    username is not part of the spec but included for convenience
    """

    timeStart = jsonobject.DateTimeProperty()
    timeEnd = jsonobject.DateTimeProperty()
    instanceID = jsonobject.StringProperty()
    userID = jsonobject.StringProperty()
    deviceID = jsonobject.StringProperty()
    deprecatedID = jsonobject.StringProperty()
    username = jsonobject.StringProperty()
    appVersion = jsonobject.StringProperty()
    location = GeoPointProperty()


class CommCareCaseSQL(models.Model, AbstractCommCareCase, RedisLockableMixIn):
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

    def __get_case_id(self):
        return self.case_uuid

    def __set_case_id(self, _id):
        self.case_uuid = _id

    case_id = property(__get_case_id, __set_case_id)

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

    @classmethod
    def get_obj_id(cls, obj):
        return obj.case_uuid

    @classmethod
    def get_obj_by_id(cls, _id):
        return cls.get(_id)

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

    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=True,
        related_name="indices", related_query_name="index"
    )
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
