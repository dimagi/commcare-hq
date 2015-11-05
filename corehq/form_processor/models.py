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

from .abstract_models import AbstractXFormInstance
from .exceptions import XFormNotFound


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

Attachment = collections.namedtuple('Attachment', 'name content content_type')
