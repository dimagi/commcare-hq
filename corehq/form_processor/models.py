from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import mimetypes
import os
import sys
import uuid
import functools
from collections import (
    namedtuple,
    OrderedDict
)
from contextlib import contextmanager
from datetime import datetime

import attr
import six
from io import BytesIO
from django.db import models
from jsonfield.fields import JSONField
from jsonobject import JsonObject
from jsonobject import StringProperty
from jsonobject.properties import BooleanProperty
from PIL import Image
from six.moves import map
from lxml import etree

from corehq.apps.sms.mixin import MessagingCaseContactMixin
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.atomic import AtomicBlobs
from corehq.blobs.exceptions import NotFound, BadName
from corehq.blobs.models import BlobMeta
from corehq.blobs.util import get_content_md5
from corehq.form_processor.abstract_models import DEFAULT_PARENT_IDENTIFIER
from corehq.form_processor.exceptions import UnknownActionType
from corehq.form_processor.track_related import TrackRelatedChanges
from corehq.apps.tzmigration.api import force_phone_timezones_should_be_processed
from corehq.sql_db.models import PartitionedModel, RestrictedManager
from corehq.util.json import CommCareJSONEncoder
from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty
from couchforms.signals import xform_archived, xform_unarchived
from dimagi.ext import jsonobject
from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.couch.undo import DELETED_SUFFIX
from memoized import memoized
from .abstract_models import AbstractXFormInstance, AbstractCommCareCase, IsImageMixin
from .exceptions import AttachmentNotFound

XFormInstanceSQL_DB_TABLE = 'form_processor_xforminstancesql'
XFormOperationSQL_DB_TABLE = 'form_processor_xformoperationsql'

CommCareCaseSQL_DB_TABLE = 'form_processor_commcarecasesql'
CommCareCaseIndexSQL_DB_TABLE = 'form_processor_commcarecaseindexsql'
CaseAttachmentSQL_DB_TABLE = 'form_processor_caseattachmentsql'
CaseTransaction_DB_TABLE = 'form_processor_casetransaction'
LedgerValue_DB_TABLE = 'form_processor_ledgervalue'
LedgerTransaction_DB_TABLE = 'form_processor_ledgertransaction'

CaseAction = namedtuple("CaseAction", ["action_type", "updated_known_properties", "indices"])


class TruncatingCharField(models.CharField):
    """
    http://stackoverflow.com/a/3460942
    """

    def get_prep_value(self, value):
        value = super(TruncatingCharField, self).get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value


@attr.s
class Attachment(IsImageMixin):
    """Unsaved form attachment

    This class implements the subset of the `BlobMeta` interface needed
    when handling attachments before they are saved.
    """

    name = attr.ib()
    raw_content = attr.ib(repr=False)
    content_type = attr.ib()
    properties = attr.ib(default=None)

    def __attrs_post_init__(self):
        """This is necessary for case attachments

        DO NOT USE `self.key` OR `self.properties`; they are only
        referenced when creating case attachments, which are slated for
        removal. The `properties` calculation should be moved back into
        `write()` when case attachments are removed.
        """
        self.key = uuid.uuid4().hex
        if self.properties is None:
            self.properties = {}
            if self.is_image:
                try:
                    img_size = Image.open(self.open()).size
                    self.properties.update(width=img_size[0], height=img_size[1])
                except IOError:
                    self.content_type = 'application/octet-stream'

    @property
    @memoized
    def content_length(self):
        """This is necessary for case attachments

        DO NOT USE THIS. It is only referenced when creating case
        attachments, which are slated for removal.
        """
        if isinstance(self.raw_content, bytes):
            return len(self.raw_content)
        if isinstance(self.raw_content, six.text_type):
            return len(self.raw_content.encode('utf-8'))
        pos = self.raw_content.tell()
        try:
            self.raw_content.seek(0, os.SEEK_END)
            return self.raw_content.tell()
        finally:
            self.raw_content.seek(pos)

    @property
    @memoized
    def content(self):
        """Get content bytes

        This is not part of the `BlobMeta` interface. Avoid this method
        for large attachments because it reads the entire attachment
        content into memory.
        """
        if hasattr(self.raw_content, 'read'):
            if hasattr(self.raw_content, 'seek'):
                self.raw_content.seek(0)
            data = self.raw_content.read()
        else:
            data = self.raw_content

        if isinstance(data, six.text_type):
            data = data.encode("utf-8")
        return data

    def open(self):
        """Get a file-like object with attachment content

        This is the preferred way to read attachment content.

        If the underlying raw content is a django `File` object this
        will call `raw_content.open()`, which changes the state of the
        underlying file object and will affect other concurrent readers
        (it is not safe to use this for multiple concurrent reads).
        """
        if isinstance(self.raw_content, (bytes, six.text_type)):
            return BytesIO(self.content)
        fileobj = self.raw_content.open()

        if fileobj is None:
            assert not isinstance(self.raw_content, BlobMeta), repr(self)
            # work around Django 1.11 bug, fixed in 2.0
            # https://github.com/django/django/blob/1.11.15/django/core/files/base.py#L131-L137
            # https://github.com/django/django/blob/2.0/django/core/files/base.py#L128
            return self.raw_content

        return fileobj

    @memoized
    def content_md5(self):
        """Get RFC-1864-compliant Content-MD5 header value"""
        return get_content_md5(self.open())

    def write(self, blob_db, xform):
        """Save attachment

        This is not part of the `BlobMeta` interface.

        This will create an orphaned blob if the xform is not saved.
        If this is called in a SQL transaction and the transaction is
        rolled back, then there will be no record of the blob (blob
        metadata will be lost), but the blob content will continue to
        use space in the blob db unless something like `AtomicBlobs` is
        used to clean up on rollback.

        :param blob_db: Blob db where content will be written.
        :param xform: The XForm instance associated with this attachment.
        :returns: `BlobMeta` object.
        """
        return blob_db.put(
            self.open(),
            key=self.key,
            domain=xform.domain,
            parent_id=xform.form_id,
            type_code=(CODES.form_xml if self.name == "form.xml" else CODES.form_attachment),
            name=self.name,
            content_type=self.content_type,
            properties=self.properties,
        )


class SaveStateMixin(object):

    def is_saved(self):
        return bool(self._get_pk_val())


class AttachmentMixin(SaveStateMixin):
    """Mixin for models that have attachments

    This class has some features that are not used by all subclasses.
    For example cases never have unsaved attachments, and therefore never
    write attachments.
    """

    @property
    def attachments_list(self):
        try:
            rval = self._attachments_list
        except AttributeError:
            rval = self._attachments_list = []
        return rval

    @attachments_list.setter
    def attachments_list(self, value):
        assert not hasattr(self, "_attachments_list"), self._attachments_list
        self._attachments_list = value

    def copy_attachments(self, xform):
        """Copy attachments from the given xform"""
        existing_names = {a.name for a in self.attachments_list}
        self.attachments_list.extend(
            Attachment(meta.name, meta, meta.content_type, meta.properties)
            for meta in six.itervalues(xform.attachments)
            if meta.name not in existing_names
        )

    def has_unsaved_attachments(self):
        """Return true if this form has unsaved attachments else false"""
        return any(isinstance(a, Attachment) for a in self.attachments_list)

    def attachment_writer(self):
        """Context manager for atomically writing attachments

        Usage:
            with form.attachment_writer() as write_attachments, \\
                    transaction.atomic(using=form.db, savepoint=False):
                form.save()
                write_attachments()
                ...
        """
        if all(isinstance(a, BlobMeta) for a in self.attachments_list):
            # do nothing if all attachments have already been written
            @contextmanager
            def noop_context():
                yield lambda: None

            return noop_context()

        def write_attachments(blob_db):
            self._attachments_list = [
                attachment.write(blob_db, self)
                for attachment in self.attachments_list
            ]

        @contextmanager
        def atomic_attachments():
            unsaved = self.attachments_list
            assert all(isinstance(a, Attachment) for a in unsaved), unsaved
            with AtomicBlobs(get_blob_db()) as blob_db:
                yield lambda: write_attachments(blob_db)

        return atomic_attachments()

    def get_attachments(self):
        attachments = getattr(self, '_attachments_list', None)
        if attachments is not None:
            return attachments

        if self.is_saved():
            return self._get_attachments_from_db()
        return []

    def get_attachment(self, attachment_name):
        """Read attachment content

        Avoid this method because it reads the entire attachment into
        memory at once.
        """
        attachment = self.get_attachment_meta(attachment_name)
        if not attachment:
            raise AttachmentNotFound(attachment_name)
        with attachment.open() as content:
            return content.read()

    def get_attachment_meta(self, attachment_name):
        def _get_attachment_from_list(attachments):
            for attachment in attachments:
                if attachment.name == attachment_name:
                    return attachment

        attachments = getattr(self, '_attachments_list', None)
        if attachments is not None:
            return _get_attachment_from_list(attachments)

        if self.is_saved():
            return self._get_attachment_from_db(attachment_name)

    def _get_attachment_from_db(self, attachment_name):
        raise NotImplementedError

    def _get_attachments_from_db(self):
        raise NotImplementedError


@six.python_2_unicode_compatible
class XFormInstanceSQL(PartitionedModel, models.Model, RedisLockableMixIn, AttachmentMixin,
                       AbstractXFormInstance, TrackRelatedChanges):
    partition_attr = 'form_id'
    objects = RestrictedManager()

    # states should be powers of 2
    NORMAL = 1
    ARCHIVED = 2
    DEPRECATED = 4
    DUPLICATE = 8
    ERROR = 16
    SUBMISSION_ERROR_LOG = 32
    DELETED = 64
    STATES = (
        (NORMAL, 'normal'),
        (ARCHIVED, 'archived'),
        (DEPRECATED, 'deprecated'),
        (DUPLICATE, 'duplicate'),
        (ERROR, 'error'),
        (SUBMISSION_ERROR_LOG, 'submission_error'),
        (DELETED, 'deleted'),
    )

    form_id = models.CharField(max_length=255, unique=True, db_index=True, default=None)

    domain = models.CharField(max_length=255, default=None)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255, default=None)
    user_id = models.CharField(max_length=255, null=True)

    # When a form is deprecated, the existing form receives a new id and its original id is stored in orig_id
    orig_id = models.CharField(max_length=255, null=True)

    # When a form is deprecated, the new form gets a reference to the deprecated form
    deprecated_form_id = models.CharField(max_length=255, null=True)

    server_modified_on = models.DateTimeField(db_index=True, auto_now=True, null=True)

    # The time at which the server has received the form
    received_on = models.DateTimeField(db_index=True)

    # Stores the datetime of when a form was deprecated
    edited_on = models.DateTimeField(null=True)

    deleted_on = models.DateTimeField(null=True)
    deletion_id = models.CharField(max_length=255, null=True)

    auth_context = JSONField(default=dict)
    openrosa_headers = JSONField(default=dict)

    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    partial_submission = models.BooleanField(default=False)
    submit_ip = models.CharField(max_length=255, null=True)
    last_sync_token = models.CharField(max_length=255, null=True)
    problem = models.TextField(null=True)
    date_header = models.DateTimeField(null=True)
    build_id = models.CharField(max_length=255, null=True)
    state = models.PositiveSmallIntegerField(choices=STATES, default=NORMAL)
    initial_processing_complete = models.BooleanField(default=False)

    # for compatability with corehq.blobs.mixin.DeferredBlobMixin interface
    persistent_blobs = None

    # form meta properties
    time_end = models.DateTimeField(null=True, blank=True)
    time_start = models.DateTimeField(null=True, blank=True)
    commcare_version = models.CharField(max_length=8, blank=True, null=True)
    app_version = models.PositiveIntegerField(null=True, blank=True)

    def __init__(self, *args, **kwargs):
        super(XFormInstanceSQL, self).__init__(*args, **kwargs)
        # keep track to avoid refetching to check whether value is updated
        self.__original_form_id = self.form_id

    def form_id_updated(self):
        return self.__original_form_id != self.form_id

    @property
    def original_form_id(self):
        """Form ID before it was updated"""
        return self.__original_form_id

    @property
    @memoized
    def original_operations(self):
        """
        Returns operations based on self.__original_form_id, useful
            to lookup correct attachments while modifying self.form_id
        """
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        return FormAccessorSQL.get_form_operations(self.__original_form_id)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.form_id

    @classmethod
    def get_obj_id(cls, obj):
        return obj.form_id

    @classmethod
    def get_obj_by_id(cls, form_id):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        return FormAccessorSQL.get_form(form_id)

    @property
    def get_id(self):
        return self.form_id

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
    def is_deleted(self):
        # deleting a form adds the deleted state to the current state
        # in order to support restoring the pre-deleted state.
        return self.state & self.DELETED == self.DELETED

    @property
    def doc_type(self):
        """Comparability with couch forms"""
        from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
        if self.is_deleted:
            return 'XFormInstance' + DELETED_SUFFIX
        return {v: k for k, v in doc_type_to_state.items()}.get(self.state, 'XFormInstance')

    @property
    @memoized
    def attachments(self):
        from couchforms.const import ATTACHMENT_NAME
        return {att.name: att for att in self.get_attachments() if att.name != ATTACHMENT_NAME}

    @property
    @memoized
    def serialized_attachments(self):
        from .serializers import XFormAttachmentSQLSerializer
        return {
            att.name: XFormAttachmentSQLSerializer(att).data
            for att in self.get_attachments()
        }

    @property
    @memoized
    def form_data(self):
        """Returns the JSON representation of the form XML"""
        from couchforms import XMLSyntaxError
        from .utils import convert_xform_to_json, adjust_datetimes
        from corehq.form_processor.utils.metadata import scrub_form_meta
        xml = self.get_xml()
        try:
            form_json = convert_xform_to_json(xml)
        except XMLSyntaxError:
            return {}
        # we can assume all sql domains are new timezone domains
        with force_phone_timezones_should_be_processed():
            adjust_datetimes(form_json)

        scrub_form_meta(self.form_id, form_json)
        return form_json

    @property
    @memoized
    def history(self):
        """:returns: List of XFormOperationSQL objects"""
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        operations = FormAccessorSQL.get_form_operations(self.form_id) if self.is_saved() else []
        operations += self.get_tracked_models_to_create(XFormOperationSQL)
        return operations

    @property
    def metadata(self):
        from .utils import clean_metadata
        if const.TAG_META in self.form_data:
            return XFormPhoneMetadata.wrap(clean_metadata(self.form_data[const.TAG_META]))

    def soft_delete(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        FormAccessorSQL.soft_delete_forms(self.domain, [self.form_id])
        self.state |= self.DELETED

    def to_json(self, include_attachments=False):
        from .serializers import XFormInstanceSQLSerializer, lazy_serialize_form_attachments, \
            lazy_serialize_form_history
        serializer = XFormInstanceSQLSerializer(self)
        data = dict(serializer.data)
        if include_attachments:
            data['external_blobs'] = lazy_serialize_form_attachments(self)
        data['history'] = lazy_serialize_form_history(self)
        data['backend_id'] = 'sql'
        return data

    def _get_attachment_from_db(self, attachment_name):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        return FormAccessorSQL.get_attachment_by_name(self.form_id, attachment_name)

    def _get_attachments_from_db(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        return FormAccessorSQL.get_attachments(self.form_id)

    def get_xml_element(self):
        xml = self.get_xml()
        if not xml:
            return None
        return etree.fromstring(xml)

    def get_data(self, path):
        """
        Evaluates an xpath expression like: path/to/node and returns the value
        of that element, or None if there is no value.
        :param path: xpath like expression
        """
        return safe_index({'form': self.form_data}, path.split("/"))

    @memoized
    def get_xml(self):
        return self.get_attachment('form.xml')

    def xml_md5(self):
        return self.get_attachment_meta('form.xml').content_md5()

    def archive(self, user_id=None, trigger_signals=True):
        # If this archive was initiated by a user, delete all other stubs for this action so that this action
        # isn't overridden
        if self.is_archived:
            return
        from couchforms.models import UnfinishedArchiveStub
        UnfinishedArchiveStub.objects.filter(xform_id=self.form_id).all().delete()
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        from corehq.form_processor.submission_process_tracker import unfinished_archive
        with unfinished_archive(instance=self, user_id=user_id, archive=True) as archive_stub:
            FormAccessorSQL.archive_form(self, user_id)
            archive_stub.archive_history_updated()
            if trigger_signals:
                xform_archived.send(sender="form_processor", xform=self)

    def unarchive(self, user_id=None, trigger_signals=True):
        # If this unarchive was initiated by a user, delete all other stubs for this action so that this action
        # isn't overridden
        if not self.is_archived:
            return
        from couchforms.models import UnfinishedArchiveStub
        UnfinishedArchiveStub.objects.filter(user_id=user_id).all().delete()
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        from corehq.form_processor.submission_process_tracker import unfinished_archive
        with unfinished_archive(instance=self, user_id=user_id, archive=False) as archive_stub:
            FormAccessorSQL.unarchive_form(self, user_id)
            archive_stub.archive_history_updated()
            if trigger_signals:
                xform_unarchived.send(sender="form_processor", xform=self)

    def publish_archive_action_to_kafka(self, user_id, archive, trigger_signals=True):
        # Don't update the history, just send to kafka
        from couchforms.models import UnfinishedArchiveStub
        from corehq.form_processor.submission_process_tracker import unfinished_archive
        from corehq.form_processor.change_publishers import publish_form_saved
        # Delete the original stub
        UnfinishedArchiveStub.objects.filter(xform_id=self.form_id).all().delete()
        if trigger_signals:
            with unfinished_archive(instance=self, user_id=user_id, archive=archive):
                if archive:
                    xform_archived.send(sender="form_processor", xform=self)
                else:
                    xform_unarchived.send(sender="form_processor", xform=self)
                publish_form_saved(self)

    def __str__(self):
        return (
            "{f.doc_type}("
            "form_id='{f.form_id}', "
            "domain='{f.domain}', "
            "xmlns='{f.xmlns}', "
            ")"
        ).format(f=self)

    class Meta(object):
        db_table = XFormInstanceSQL_DB_TABLE
        app_label = "form_processor"
        index_together = [
            ('domain', 'state'),
            ('domain', 'user_id'),
        ]
        indexes = [
            models.Index(['xmlns'])
        ]


class DeprecatedXFormAttachmentSQL(models.Model):
    """Deprecated: moved to BlobMeta

    This class exists so Django does not delete its table when making
    new migrations. It should not be referenced anywhere.
    """
    form_id = models.CharField(max_length=255)
    attachment_id = models.UUIDField(unique=True, db_index=True)
    content_type = models.CharField(max_length=255, null=True)
    content_length = models.IntegerField(null=True)
    blob_id = models.CharField(max_length=255, default=None)
    blob_bucket = models.CharField(max_length=255, null=True, default=None)
    name = models.CharField(max_length=255, default=None)
    md5 = models.CharField(max_length=255, default=None)
    properties = JSONField(default=dict)

    class Meta(object):
        db_table = "form_processor_xformattachmentsql"
        app_label = "form_processor"
        index_together = [
            ("form_id", "name"),
        ]


class XFormOperationSQL(PartitionedModel, SaveStateMixin, models.Model):
    partition_attr = 'form_id'
    objects = RestrictedManager()

    ARCHIVE = 'archive'
    UNARCHIVE = 'unarchive'
    EDIT = 'edit'
    UUID_DATA_FIX = 'uuid_data_fix'
    GDPR_SCRUB = 'gdpr_scrub'

    form = models.ForeignKey(XFormInstanceSQL, to_field='form_id', on_delete=models.CASCADE)
    user_id = models.CharField(max_length=255, null=True)
    operation = models.CharField(max_length=255, default=None)
    date = models.DateTimeField(null=False)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.form, self.user_id, self.date

    @property
    def user(self):
        return self.user_id

    class Meta(object):
        app_label = "form_processor"
        db_table = XFormOperationSQL_DB_TABLE


class XFormPhoneMetadata(jsonobject.JsonObject):
    """
    Metadata of an xform, from a meta block structured like:

        <Meta>
            <timeStart />
            <timeEnd />
            <instanceID />
            <userID />
            <deviceID />
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
    username = jsonobject.StringProperty()
    appVersion = jsonobject.StringProperty()
    location = GeoPointProperty()

    @property
    def commcare_version(self):
        from corehq.apps.receiverwrapper.util import get_commcare_version_from_appversion_text
        from distutils.version import LooseVersion
        version_text = get_commcare_version_from_appversion_text(self.appVersion)
        if version_text:
            return LooseVersion(version_text)


class SupplyPointCaseMixin(object):
    CASE_TYPE = 'supply-point'

    @property
    @memoized
    def location(self):
        from corehq.apps.locations.models import SQLLocation
        if self.location_id is None:
            return None
        try:
            return self.sql_location
        except SQLLocation.DoesNotExist:
            return None

    @property
    def sql_location(self):
        from corehq.apps.locations.models import SQLLocation
        return SQLLocation.objects.get(location_id=self.location_id)


@six.python_2_unicode_compatible
class CommCareCaseSQL(PartitionedModel, models.Model, RedisLockableMixIn,
                      AttachmentMixin, AbstractCommCareCase, TrackRelatedChanges,
                      SupplyPointCaseMixin, MessagingCaseContactMixin):
    partition_attr = 'case_id'
    objects = RestrictedManager()

    case_id = models.CharField(max_length=255, unique=True, db_index=True)
    domain = models.CharField(max_length=255, default=None)
    type = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True)

    owner_id = models.CharField(max_length=255, null=False)

    opened_on = models.DateTimeField(null=True)
    opened_by = models.CharField(max_length=255, null=True)

    modified_on = models.DateTimeField(null=False)
    # represents the max date from all case transactions
    server_modified_on = models.DateTimeField(null=False, db_index=True)
    modified_by = models.CharField(max_length=255)

    closed = models.BooleanField(default=False, null=False)
    closed_on = models.DateTimeField(null=True)
    closed_by = models.CharField(max_length=255, null=True)

    deleted = models.BooleanField(default=False, null=False)
    deleted_on = models.DateTimeField(null=True)
    deletion_id = models.CharField(max_length=255, null=True)

    external_id = models.CharField(max_length=255, null=True)
    location_id = models.CharField(max_length=255, null=True)

    case_json = JSONField(default=dict)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.case_id

    @property
    def doc_type(self):
        dt = 'CommCareCase'
        if self.is_deleted:
            dt += DELETED_SUFFIX
        return dt

    @property
    def get_id(self):
        return self.case_id

    def set_case_id(self, case_id):
        self.case_id = case_id

    @property
    @memoized
    def xform_ids(self):
        return [t.form_id for t in self.transactions if not t.revoked and t.is_form_transaction]

    @property
    def user_id(self):
        return self.modified_by

    @user_id.setter
    def user_id(self, value):
        self.modified_by = value

    def soft_delete(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        CaseAccessorSQL.soft_delete_cases(self.domain, [self.case_id])
        self.deleted = True

    @property
    def is_deleted(self):
        return self.deleted

    def dynamic_case_properties(self):
        return OrderedDict(sorted(six.iteritems(self.case_json)))

    def to_api_json(self, lite=False):
        from .serializers import CommCareCaseSQLAPISerializer
        serializer = CommCareCaseSQLAPISerializer(self, lite=lite)
        return serializer.data

    def to_json(self):
        from .serializers import (
            CommCareCaseSQLSerializer, lazy_serialize_case_indices, lazy_serialize_case_transactions,
            lazy_serialize_case_xform_ids, lazy_serialize_case_attachments
        )
        serializer = CommCareCaseSQLSerializer(self)
        ret = dict(serializer.data)
        ret['indices'] = lazy_serialize_case_indices(self)
        ret['actions'] = lazy_serialize_case_transactions(self)
        ret['xform_ids'] = lazy_serialize_case_xform_ids(self)
        ret['case_attachments'] = lazy_serialize_case_attachments(self)
        for key in self.case_json:
            if key not in ret:
                ret[key] = self.case_json[key]
        ret['backend_id'] = 'sql'
        return ret

    def dumps(self, pretty=False):
        indent = 4 if pretty else None
        return json.dumps(self.to_json(), indent=indent, cls=CommCareJSONEncoder)

    def pprint(self):
        print(self.dumps(pretty=True))

    @property
    @memoized
    def reverse_indices(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_reverse_indices(self.domain, self.case_id)

    @memoized
    def get_subcases(self, index_identifier=None):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        subcase_ids = [
            ix.referenced_id for ix in self.reverse_indices
            if (index_identifier is None or ix.identifier == index_identifier)
        ]
        return list(CaseAccessorSQL.get_cases(subcase_ids))

    def get_reverse_index_map(self):
        return self.get_index_map(True)

    @memoized
    def _saved_indices(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        cached_indices = 'cached_indices'
        if hasattr(self, cached_indices):
            return getattr(self, cached_indices)

        return CaseAccessorSQL.get_indices(self.domain, self.case_id) if self.is_saved() else []

    @property
    def indices(self):
        indices = self._saved_indices()

        to_delete = [
            (to_delete.id, to_delete.identifier)
            for to_delete in self.get_tracked_models_to_delete(CommCareCaseIndexSQL)
        ]
        indices = [index for index in indices if (index.id, index.identifier) not in to_delete]

        indices += self.get_tracked_models_to_create(CommCareCaseIndexSQL)

        return indices

    @property
    def has_indices(self):
        return self.indices or self.reverse_indices

    def has_index(self, index_id):
        return any(index.identifier == index_id for index in self.indices)

    def get_index(self, index_id):
        found = [i for i in self.indices if i.identifier == index_id]
        if found:
            assert(len(found) == 1)
            return found[0]
        return None

    def _get_attachment_from_db(self, name):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_attachment_by_name(self.case_id, name)

    def _get_attachments_from_db(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_attachments(self.case_id)

    @property
    @memoized
    def transactions(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        transactions = CaseAccessorSQL.get_transactions(self.case_id) if self.is_saved() else []
        transactions += self.get_tracked_models_to_create(CaseTransaction)
        return transactions

    def check_transaction_order(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.check_transaction_order_for_case(self.case_id)

    @property
    def actions(self):
        """For compatability with CommCareCase. Please use transactions when possible"""
        return self.non_revoked_transactions

    def get_transaction_by_form_id(self, form_id):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        transactions = [t for t in self.get_tracked_models_to_create(CaseTransaction) if t.form_id == form_id]
        assert len(transactions) <= 1
        transaction = transactions[0] if transactions else None

        if not transaction:
            transaction = CaseAccessorSQL.get_transaction_by_form_id(self.case_id, form_id)
        return transaction

    @property
    def non_revoked_transactions(self):
        return [t for t in self.transactions if not t.revoked]

    @property
    @memoized
    def case_attachments(self):
        return {attachment.name: attachment for attachment in self.get_attachments()}

    @property
    @memoized
    def serialized_attachments(self):
        from .serializers import CaseAttachmentSQLSerializer
        return {
            att.name: dict(CaseAttachmentSQLSerializer(att).data)
            for att in self.get_attachments()
            }

    @memoized
    def get_closing_transactions(self):
        return self._transactions_by_type(CaseTransaction.TYPE_FORM | CaseTransaction.TYPE_CASE_CLOSE)

    @memoized
    def get_opening_transactions(self):
        return self._transactions_by_type(CaseTransaction.TYPE_FORM | CaseTransaction.TYPE_CASE_CREATE)

    @memoized
    def get_form_transactions(self):
        return self._transactions_by_type(CaseTransaction.TYPE_FORM)

    def _transactions_by_type(self, transaction_type):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        if self.is_saved():
            transactions = CaseAccessorSQL.get_transactions_by_type(self.case_id, transaction_type)
        else:
            transactions = []
        transactions += [t for t in self.get_tracked_models_to_create(CaseTransaction) if (t.type & transaction_type) == transaction_type]
        return transactions

    def modified_since_sync(self, sync_log):
        if self.server_modified_on >= sync_log.date:
            # check all of the transactions since last sync for one that had a different sync token
            from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
            return CaseAccessorSQL.case_has_transactions_since_sync(self.case_id, sync_log._id, sync_log.date)
        return False

    def get_actions_for_form(self, xform):
        from casexml.apps.case.xform import get_case_updates
        updates = [u for u in get_case_updates(xform) if u.id == self.case_id]
        actions = [a for update in updates for a in update.actions]
        normalized_actions = [
            CaseAction(
                action_type=a.action_type_slug,
                updated_known_properties=a.get_known_properties(),
                indices=a.indices
            ) for a in actions
        ]
        return normalized_actions

    def get_case_property(self, property):
        if property in self.case_json:
            return self.case_json[property]

        allowed_fields = [
            field.name for field in self._meta.fields
            if field.name not in ('id', 'case_json')
        ]
        if property in allowed_fields:
            return getattr(self, property)

    def on_tracked_models_cleared(self, model_class=None):
        self._saved_indices.reset_cache(self)

    @classmethod
    def get_obj_id(cls, obj):
        return obj.case_id

    @classmethod
    def get_obj_by_id(cls, case_id):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_case(case_id)

    @memoized
    def get_parent(self, identifier=None, relationship=None):
        indices = self.indices

        if identifier:
            indices = [index for index in indices if index.identifier == identifier]

        if relationship:
            indices = [index for index in indices if index.relationship_id == relationship]

        return [index.referenced_case for index in indices]

    @property
    def parent(self):
        """
        Returns the parent case if one exists, else None.
        NOTE: This property should only return the first parent in the list
        of indices. If for some reason your use case creates more than one,
        please write/use a different property.
        """
        result = self.get_parent(
            identifier=DEFAULT_PARENT_IDENTIFIER,
            relationship=CommCareCaseIndexSQL.CHILD
        )
        return result[0] if result else None

    @property
    def host(self):
        result = self.get_parent(relationship=CommCareCaseIndexSQL.EXTENSION)
        return result[0] if result else None

    def __str__(self):
        return (
            "CommCareCase("
            "case_id='{c.case_id}', "
            "domain='{c.domain}', "
            "closed={c.closed}, "
            "owner_id='{c.owner_id}', "
            "server_modified_on='{c.server_modified_on}')"
        ).format(c=self)

    class Meta(object):
        index_together = [
            ["owner_id", "server_modified_on"],
            ["domain", "owner_id", "closed"],
            ["domain", "external_id", "type"],
            ["domain", "type"],
        ]
        app_label = "form_processor"
        db_table = CommCareCaseSQL_DB_TABLE


@six.python_2_unicode_compatible
class CaseAttachmentSQL(PartitionedModel, models.Model, SaveStateMixin, IsImageMixin):
    """Case attachment

    Case attachments reference form attachments, and therefore this
    model is not sole the owner of the attachment content (blob). The
    form is the primary owner, and attachment content should not be
    deleted when a case attachment is deleted unless the form attachment
    is also being deleted. All case attachment data, except for
    `attachment_id`, `case_id`, and `name`, is a copy of the same data
    from the corresponding form attachment. It is mirrored here (rather
    than simply referencing the corresponding form attachment record)
    for sharding locality with other data from the same case.
    """
    partition_attr = 'case_id'
    objects = RestrictedManager()

    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=False,
        related_name="attachment_set", related_query_name="attachment",
        on_delete=models.CASCADE,
    )
    attachment_id = models.UUIDField(unique=True, db_index=True)
    name = models.CharField(max_length=255, default=None)
    content_type = models.CharField(max_length=255, null=True)
    content_length = models.IntegerField(null=True)
    properties = JSONField(default=dict)
    blob_id = models.CharField(max_length=255, default=None)
    blob_bucket = models.CharField(max_length=255, null=True, default="")

    # DEPRECATED - use CaseAttachmentSQL.content_md5() instead
    md5 = models.CharField(max_length=255, default="")

    @property
    def key(self):
        if self.blob_bucket == "":
            # empty string in bucket -> blob_id is blob key
            return self.blob_id
        # deprecated key construction. will be removed after migration
        if self.blob_bucket is not None:
            bucket = self.blob_bucket
        else:
            if self.attachment_id is None:
                raise AttachmentNotFound("cannot manipulate attachment on unidentified document")
            bucket = os.path.join('case', self.attachment_id.hex)
        return os.path.join(bucket, self.blob_id)

    @key.setter
    def key(self, value):
        self.blob_id = value
        self.blob_bucket = ""

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.attachment_id

    def from_form_attachment(self, attachment, attachment_src):
        """
        Update fields in this attachment with fields from another attachment

        :param attachment: BlobMeta object.
        :param attachment_src: Attachment file name. Used for content type
        guessing if the form attachment has no content type.
        """
        self.key = attachment.key
        self.content_length = attachment.content_length
        self.content_type = attachment.content_type
        self.properties = attachment.properties

        if not self.content_type and attachment_src:
            guessed = mimetypes.guess_type(attachment_src)
            if len(guessed) > 0 and guessed[0] is not None:
                self.content_type = guessed[0]

    @classmethod
    def new(cls, name):
        return cls(name=name, attachment_id=uuid.uuid4())

    def __str__(self):
        return six.text_type(
            "CaseAttachmentSQL("
            "attachment_id='{a.attachment_id}', "
            "case_id='{a.case_id}', "
            "name='{a.name}', "
            "content_type='{a.content_type}', "
            "content_length='{a.content_length}', "
            "key='{a.key}', "
            "properties='{a.properties}')"
        ).format(a=self)

    def open(self):
        try:
            return get_blob_db().get(key=self.key)
        except (KeyError, NotFound, BadName):
            raise AttachmentNotFound(self.name)

    @memoized
    def content_md5(self):
        """Get RFC-1864-compliant Content-MD5 header value"""
        with self.open() as fileobj:
            return get_content_md5(fileobj)

    class Meta(object):
        app_label = "form_processor"
        db_table = CaseAttachmentSQL_DB_TABLE
        index_together = [
            ["case", "name"],
        ]


@six.python_2_unicode_compatible
class CommCareCaseIndexSQL(PartitionedModel, models.Model, SaveStateMixin):
    partition_attr = 'case_id'
    objects = RestrictedManager()

    # relationship_ids should be powers of 2
    CHILD = 1
    EXTENSION = 2
    RELATIONSHIP_CHOICES = (
        (CHILD, 'child'),
        (EXTENSION, 'extension'),
    )
    RELATIONSHIP_INVERSE_MAP = dict(RELATIONSHIP_CHOICES)
    RELATIONSHIP_MAP = {v: k for k, v in RELATIONSHIP_CHOICES}

    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=False,
        related_name="index_set", related_query_name="index",
        on_delete=models.CASCADE,
    )
    domain = models.CharField(max_length=255, default=None)
    identifier = models.CharField(max_length=255, default=None)
    referenced_id = models.CharField(max_length=255, default=None)
    referenced_type = models.CharField(max_length=255, default=None)
    relationship_id = models.PositiveSmallIntegerField(choices=RELATIONSHIP_CHOICES)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.domain, self.case, self.identifier

    @property
    @memoized
    def referenced_case(self):
        """
        For a 'forward' index this is the case that the the index points to.
        For a 'reverse' index this is the case that owns the index.
        See ``CaseAccessorSQL.get_reverse_indices``

        :return: referenced case
        """
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_case(self.referenced_id)

    @property
    def relationship(self):
        return self.RELATIONSHIP_INVERSE_MAP[self.relationship_id]

    @relationship.setter
    def relationship(self, relationship):
        self.relationship_id = self.RELATIONSHIP_MAP[relationship]

    def __eq__(self, other):
        return isinstance(other, CommCareCaseIndexSQL) and (
            self.case_id == other.case_id and
            self.identifier == other.identifier,
            self.referenced_id == other.referenced_id,
            self.referenced_type == other.referenced_type,
            self.relationship_id == other.relationship_id,
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.case_id, self.identifier, self.referenced_id, self.relationship_id))

    def __str__(self):
        return (
            "CaseIndex("
            "case_id='{i.case_id}', "
            "domain='{i.domain}', "
            "identifier='{i.identifier}', "
            "referenced_type='{i.referenced_type}', "
            "referenced_id='{i.referenced_id}', "
            "relationship='{i.relationship})"
        ).format(i=self)

    class Meta(object):
        index_together = [
            ["domain", "case"],
            ["domain", "referenced_id"],
        ]
        unique_together = ('case', 'identifier')
        db_table = CommCareCaseIndexSQL_DB_TABLE
        app_label = "form_processor"


@six.python_2_unicode_compatible
class CaseTransaction(PartitionedModel, SaveStateMixin, models.Model):
    partition_attr = 'case_id'
    objects = RestrictedManager()

    # types should be powers of 2
    TYPE_FORM = 1
    TYPE_REBUILD_WITH_REASON = 2
    TYPE_REBUILD_USER_REQUESTED = 4
    TYPE_REBUILD_USER_ARCHIVED = 8
    TYPE_REBUILD_FORM_ARCHIVED = 16
    TYPE_REBUILD_FORM_EDIT = 32
    TYPE_LEDGER = 64
    TYPE_CASE_CREATE = 128
    TYPE_CASE_CLOSE = 256
    TYPE_CASE_INDEX = 512
    TYPE_CASE_ATTACHMENT = 1024
    TYPE_REBUILD_FORM_REPROCESS = 2048
    TYPE_CHOICES = (
        (TYPE_FORM, 'form'),
        (TYPE_REBUILD_WITH_REASON, 'rebuild_with_reason'),
        (TYPE_REBUILD_USER_REQUESTED, 'user_requested_rebuild'),
        (TYPE_REBUILD_USER_ARCHIVED, 'user_archived_rebuild'),
        (TYPE_REBUILD_FORM_ARCHIVED, 'form_archive_rebuild'),
        (TYPE_REBUILD_FORM_EDIT, 'form_edit_rebuild'),
        (TYPE_REBUILD_FORM_REPROCESS, 'form_reprocessed_rebuild'),
        (TYPE_LEDGER, 'ledger'),
        (TYPE_CASE_CREATE, 'case_create'),
        (TYPE_CASE_CLOSE, 'case_close'),
        (TYPE_CASE_ATTACHMENT, 'case_attachment'),
        (TYPE_CASE_INDEX, 'case_index'),
    )
    TYPES_TO_PROCESS = (
        TYPE_FORM,
    )
    FORM_TYPE_ACTIONS_ORDER = (
        TYPE_CASE_CREATE,
        TYPE_CASE_INDEX,
        TYPE_CASE_CLOSE,
        TYPE_CASE_ATTACHMENT,
        TYPE_LEDGER,
    )
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=False,
        related_name="transaction_set", related_query_name="transaction",
        on_delete=models.CASCADE,
    )
    form_id = models.CharField(max_length=255, null=True)  # can't be a foreign key due to partitioning
    sync_log_id = models.CharField(max_length=255, null=True)
    server_date = models.DateTimeField(null=False)
    _client_date = models.DateTimeField(null=True, db_column='client_date')
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    revoked = models.BooleanField(default=False, null=False)
    details = JSONField(default=dict)

    @property
    def client_date(self):
        if self._client_date:
            return self._client_date
        return self.server_date

    @client_date.setter
    def client_date(self, value):
        self._client_date = value

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.case, self.form_id, self.type

    @staticmethod
    def _should_process(transaction_type):
        return any(map(
            lambda type_: transaction_type & type_ == type_,
            CaseTransaction.TYPES_TO_PROCESS,
        ))

    @property
    def is_relevant(self):
        relevant = not self.revoked and CaseTransaction._should_process(self.type)
        if relevant and self.form:
            relevant = self.form.is_normal

        return relevant

    @property
    def user_id(self):
        if self.form:
            return self.form.user_id
        return None

    @property
    def form(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        if not self.form_id:
            return None
        form = getattr(self, 'cached_form', None)
        if not form:
            self.cached_form = FormAccessorSQL.get_form(self.form_id)
        return self.cached_form

    @property
    def is_form_transaction(self):
        return bool(self.TYPE_FORM & self.type)

    @property
    def is_ledger_transaction(self):
        return bool(self.is_form_transaction and self.TYPE_LEDGER & self.type)

    @property
    def is_case_create(self):
        return bool(self.is_form_transaction and self.TYPE_CASE_CREATE & self.type)

    @property
    def is_case_close(self):
        return bool(self.is_form_transaction and self.TYPE_CASE_CLOSE & self.type)

    @property
    def is_case_index(self):
        return bool(self.is_form_transaction and self.TYPE_CASE_INDEX & self.type)

    @property
    def is_case_attachment(self):
        return bool(self.is_form_transaction and self.TYPE_CASE_ATTACHMENT & self.type)

    @property
    def is_case_rebuild(self):
        return bool(self.type & self.case_rebuild_types())

    @classmethod
    @memoized
    def case_rebuild_types(cls):
        """ returns an int of all rebuild types reduced using a bitwise or """
        return functools.reduce(lambda x, y: x | y, [
            cls.TYPE_REBUILD_FORM_ARCHIVED,
            cls.TYPE_REBUILD_FORM_EDIT,
            cls.TYPE_REBUILD_USER_ARCHIVED,
            cls.TYPE_REBUILD_USER_REQUESTED,
            cls.TYPE_REBUILD_WITH_REASON,
            cls.TYPE_REBUILD_FORM_REPROCESS,
        ])

    @property
    def readable_type(self):
        readable_type = []
        for type_, type_slug in self.TYPE_CHOICES:
            if self.type & type_:
                readable_type.append(type_slug)
        return ' / '.join(readable_type)

    def __eq__(self, other):
        if not isinstance(other, CaseTransaction):
            return False

        return (
            self.case_id == other.case_id and
            self.type == other.type and
            self.form_id == other.form_id
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def form_transaction(cls, case, xform, client_date, action_types=None):
        action_types = action_types or []

        if any([not cls._valid_action_type(action_type) for action_type in action_types]):
            raise UnknownActionType('Unknown action type found')

        type_ = cls.TYPE_FORM

        for action_type in action_types:
            type_ |= action_type

        transaction = cls._from_form(case, xform, transaction_type=type_)
        transaction.client_date = client_date

        return transaction

    @classmethod
    def _valid_action_type(cls, action_type):
        return action_type in [
            cls.TYPE_CASE_CLOSE,
            cls.TYPE_CASE_INDEX,
            cls.TYPE_CASE_CREATE,
            cls.TYPE_CASE_ATTACHMENT,
            0,
        ]

    @classmethod
    def ledger_transaction(cls, case, xform):
        return cls._from_form(
            case,
            xform,
            transaction_type=CaseTransaction.TYPE_LEDGER | CaseTransaction.TYPE_FORM
        )

    @classmethod
    def _from_form(cls, case, xform, transaction_type):
        transaction = case.get_transaction_by_form_id(xform.form_id)
        if transaction:
            transaction.type |= transaction_type
            return transaction
        else:
            return CaseTransaction(
                case=case,
                form_id=xform.form_id,
                sync_log_id=xform.last_sync_token,
                server_date=xform.received_on,
                type=transaction_type,
                revoked=not xform.is_normal
            )

    @classmethod
    def type_from_action_type_slug(cls, action_type_slug):
        from casexml.apps.case import const
        return {
            const.CASE_ACTION_CLOSE: cls.TYPE_CASE_CLOSE,
            const.CASE_ACTION_CREATE: cls.TYPE_CASE_CREATE,
            const.CASE_ACTION_INDEX: cls.TYPE_CASE_INDEX,
            const.CASE_ACTION_ATTACHMENT: cls.TYPE_CASE_ATTACHMENT,
        }.get(action_type_slug, 0)

    @classmethod
    def rebuild_transaction(cls, case, detail):
        return CaseTransaction(
            case=case,
            server_date=datetime.utcnow(),
            type=detail.type,
            details=detail.to_json()
        )

    def __str__(self):
        return (
            "{self.form_id}: "
            "{self.client_date} "
            "({self.server_date}) "
            "{self.readable_type}"
        ).format(self=self)

    def __repr__(self):
        return (
            "CaseTransaction("
            "case_id='{self.case_id}', "
            "form_id='{self.form_id}', "
            "sync_log_id='{self.sync_log_id}', "
            "type='{self.type}', "
            "server_date='{self.server_date}', "
            "revoked='{self.revoked}')"
        ).format(self=self)

    class Meta(object):
        unique_together = ("case", "form_id", "type")
        ordering = ['server_date']
        db_table = CaseTransaction_DB_TABLE
        app_label = "form_processor"
        index_together = [
            ('case', 'server_date', 'sync_log_id'),
        ]
        indexes = [models.Index(['form_id'])]


class CaseTransactionDetail(JsonObject):
    _type = None

    @property
    def type(self):
        return self._type

    def __eq__(self, other):
        return self.type == other.type and self.to_json() == other.to_json()

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None


class RebuildWithReason(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_WITH_REASON
    reason = StringProperty()


class UserRequestedRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_USER_REQUESTED
    user_id = StringProperty()


class UserArchivedRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_USER_ARCHIVED
    user_id = StringProperty()


class FormArchiveRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_FORM_ARCHIVED
    form_id = StringProperty()
    archived = BooleanProperty()


class FormEditRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_FORM_EDIT
    deprecated_form_id = StringProperty()


class FormReprocessRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_FORM_EDIT
    form_id = StringProperty()


class LedgerValue(PartitionedModel, SaveStateMixin, models.Model, TrackRelatedChanges):
    """
    Represents the current state of a ledger. Supercedes StockState
    """
    partition_attr = 'case_id'
    objects = RestrictedManager()

    domain = models.CharField(max_length=255, null=False, default=None)
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=False, on_delete=models.CASCADE
    )
    # can't be a foreign key to products because of sharding.
    # also still unclear whether we plan to support ledgers to non-products
    entry_id = models.CharField(max_length=100, default=None)
    section_id = models.CharField(max_length=100, default=None)
    balance = models.IntegerField(default=0)
    last_modified = models.DateTimeField(db_index=True)
    last_modified_form_id = models.CharField(max_length=100, null=True, default=None)
    daily_consumption = models.DecimalField(max_digits=20, decimal_places=5, null=True)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.case, self.section_id, self.entry_id

    @property
    def last_modified_date(self):
        return self.last_modified

    @property
    def product_id(self):
        return self.entry_id

    @property
    def stock_on_hand(self):
        return self.balance

    @property
    def ledger_reference(self):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        return UniqueLedgerReference(
            case_id=self.case_id, section_id=self.section_id, entry_id=self.entry_id
        )

    @property
    def ledger_id(self):
        return self.ledger_reference.as_id()

    @property
    @memoized
    def location(self):
        from corehq.apps.locations.models import SQLLocation
        return SQLLocation.objects.get_or_None(supply_point_id=self.case_id)

    @property
    def location_id(self):
        return self.location.location_id if self.location else None

    def to_json(self, include_location_id=True):
        from .serializers import LedgerValueSerializer
        serializer = LedgerValueSerializer(self, include_location_id=include_location_id)
        return dict(serializer.data)

    def __repr__(self):
        return "LedgerValue(" \
               "case_id={s.case_id}, " \
               "section_id={s.section_id}, " \
               "entry_id={s.entry_id}, " \
               "balance={s.balance}".format(s=self)

    class Meta(object):
        app_label = "form_processor"
        db_table = LedgerValue_DB_TABLE
        unique_together = ("case", "section_id", "entry_id")


@six.python_2_unicode_compatible
class LedgerTransaction(PartitionedModel, SaveStateMixin, models.Model):
    partition_attr = 'case_id'
    objects = RestrictedManager()

    TYPE_BALANCE = 1
    TYPE_TRANSFER = 2
    TYPE_CHOICES = (
        (TYPE_BALANCE, 'balance'),
        (TYPE_TRANSFER, 'transfer'),
    )

    form_id = models.CharField(max_length=255, null=False)
    server_date = models.DateTimeField()
    report_date = models.DateTimeField()
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=False, on_delete=models.CASCADE
    )
    entry_id = models.CharField(max_length=100, default=None)
    section_id = models.CharField(max_length=100, default=None)

    user_defined_type = TruncatingCharField(max_length=20, null=True, blank=True)

    # change from previous balance
    delta = models.BigIntegerField(default=0)
    # new balance
    updated_balance = models.BigIntegerField(default=0)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.case, self.form_id, self.section_id, self.entry_id

    def get_consumption_transactions(self, exclude_inferred_receipts=False):
        """
        This adds in the inferred transactions for BALANCE transactions and converts
        TRANSFER transactions to ``consumption`` / ``receipts``
        :return: list of ``ConsumptionTransaction`` objects
        """
        from casexml.apps.stock.const import (
            TRANSACTION_TYPE_STOCKONHAND,
            TRANSACTION_TYPE_RECEIPTS,
            TRANSACTION_TYPE_CONSUMPTION
        )
        transactions = [
            ConsumptionTransaction(
                TRANSACTION_TYPE_RECEIPTS if self.delta > 0 else TRANSACTION_TYPE_CONSUMPTION,
                abs(self.delta),
                self.report_date
            )
        ]
        if self.type == LedgerTransaction.TYPE_BALANCE:
            if self.delta > 0 and exclude_inferred_receipts:
                transactions = []

            transactions.append(
                ConsumptionTransaction(
                    TRANSACTION_TYPE_STOCKONHAND,
                    self.updated_balance,
                    self.report_date
                )
            )
        return transactions

    @property
    def readable_type(self):
        for type_, type_slug in self.TYPE_CHOICES:
            if self.type == type_:
                return type_slug

    @property
    def ledger_reference(self):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        return UniqueLedgerReference(
            case_id=self.case_id, section_id=self.section_id, entry_id=self.entry_id
        )

    @property
    def stock_on_hand(self):
        return self.updated_balance

    def __str__(self):
        return (
            "LedgerTransaction("
            "form_id='{self.form_id}', "
            "server_date='{self.server_date}', "
            "report_date='{self.report_date}', "
            "type='{self.readable_type}', "
            "case_id='{self.case_id}', "
            "entry_id='{self.entry_id}', "
            "section_id='{self.section_id}', "
            "user_defined_type='{self.user_defined_type}', "
            "delta='{self.delta}', "
            "updated_balance='{self.updated_balance}')"
        ).format(self=self)

    class Meta(object):
        db_table = LedgerTransaction_DB_TABLE
        app_label = "form_processor"
        # note: can't put a unique constraint here (case_id, form_id, section_id, entry_id)
        # since a single form can make multiple updates to a ledger
        index_together = [
            ["case", "section_id", "entry_id"],
        ]
        indexes = [models.Index(['form_id'])]


class ConsumptionTransaction(namedtuple('ConsumptionTransaction', ['type', 'normalized_value', 'received_on'])):

    @property
    def is_stockout(self):
        from casexml.apps.stock.const import TRANSACTION_TYPE_STOCKONHAND
        return self.type == TRANSACTION_TYPE_STOCKONHAND and self.normalized_value == 0

    @property
    def is_checkpoint(self):
        from casexml.apps.stock.const import TRANSACTION_TYPE_STOCKONHAND
        return self.type == TRANSACTION_TYPE_STOCKONHAND and not self.is_stockout
