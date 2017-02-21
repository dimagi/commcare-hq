import json
import logging
import mimetypes
import os
import uuid
from collections import (
    namedtuple,
    OrderedDict
)
from datetime import datetime

from StringIO import StringIO
from django.conf import settings
from django.db import models
from jsonfield.fields import JSONField
from jsonobject import JsonObject
from jsonobject import StringProperty
from jsonobject.properties import BooleanProperty
from lxml import etree
from corehq.apps.sms.mixin import MessagingCaseContactMixin
from corehq.blobs import get_blob_db
from corehq.blobs.mixin import get_short_identifier
from corehq.blobs.exceptions import NotFound, BadName
from corehq.form_processor import signals
from corehq.form_processor.abstract_models import DEFAULT_PARENT_IDENTIFIER
from corehq.form_processor.exceptions import InvalidAttachment, UnknownActionType
from corehq.form_processor.track_related import TrackRelatedChanges
from corehq.apps.tzmigration.api import force_phone_timezones_should_be_processed
from corehq.sql_db.routers import db_for_read_write
from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty
from couchforms.signals import xform_archived, xform_unarchived
from dimagi.ext import jsonobject
from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from .abstract_models import AbstractXFormInstance, AbstractCommCareCase, CaseAttachmentMixin, IsImageMixin
from .exceptions import AttachmentNotFound, AccessRestricted

XFormInstanceSQL_DB_TABLE = 'form_processor_xforminstancesql'
XFormAttachmentSQL_DB_TABLE = 'form_processor_xformattachmentsql'
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


class Attachment(namedtuple('Attachment', 'name raw_content content_type')):

    @property
    @memoized
    def content(self):
        if hasattr(self.raw_content, 'read'):
            if hasattr(self.raw_content, 'seek'):
                self.raw_content.seek(0)
            data = self.raw_content.read()
        else:
            data = self.raw_content

        if isinstance(data, unicode):
            data = data.encode("utf-8")
        return data

    def content_as_file(self):
        return StringIO(self.content)


class SaveStateMixin(object):

    def is_saved(self):
        return bool(self._get_pk_val())


class AttachmentMixin(SaveStateMixin):
    """Requires the model to be linked to the attachments model via the 'attachments' related name.
    """
    ATTACHMENTS_RELATED_NAME = 'attachment_set'

    def get_attachments(self):
        for list_attr in ('unsaved_attachments', 'cached_attachments'):
            if hasattr(self, list_attr):
                return getattr(self, list_attr)

        if self.is_saved():
            return self._get_attachments_from_db()
        return []

    def get_attachment(self, attachment_name):
        attachment = self.get_attachment_meta(attachment_name)
        if not attachment:
            raise AttachmentNotFound(attachment_name)
        return attachment.read_content()

    def get_attachment_meta(self, attachment_name):
        def _get_attachment_from_list(attachments):
            for attachment in attachments:
                if attachment.name == attachment_name:
                    return attachment

        for list_attr in ('unsaved_attachments', 'cached_attachments'):
            if hasattr(self, list_attr):
                return _get_attachment_from_list(getattr(self, list_attr))

        if self.is_saved():
            return self._get_attachment_from_db(attachment_name)

    def _get_attachment_from_db(self, attachment_name):
        raise NotImplementedError

    def _get_attachments_from_db(self):
        raise NotImplementedError


class DisabledDbMixin(object):

    def save(self, *args, **kwargs):
        raise AccessRestricted('Direct object save disabled.')

    def save_base(self, *args, **kwargs):
        raise AccessRestricted('Direct object save disabled.')

    def delete(self, *args, **kwargs):
        raise AccessRestricted('Direct object deletion disabled.')


class RestrictedManager(models.Manager):

    def get_queryset(self):
        if not getattr(settings, 'ALLOW_FORM_PROCESSING_QUERIES', False):
            raise AccessRestricted('Only "raw" queries allowed')
        else:
            return super(RestrictedManager, self).get_queryset()

    def raw(self, raw_query, params=None, translations=None, using=None):
        from django.db.models.query import RawQuerySet
        if not using:
            using = db_for_read_write(self.model)
        return RawQuerySet(raw_query, model=self.model,
                params=params, translations=translations,
                using=using)


class XFormInstanceSQL(DisabledDbMixin, models.Model, RedisLockableMixIn, AttachmentMixin,
                       AbstractXFormInstance, TrackRelatedChanges):
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

    # Stores the datetime of when a form was deprecated
    edited_on = models.DateTimeField(null=True)

    # The time at which the server has received the form
    received_on = models.DateTimeField(db_index=True)

    auth_context = JSONField(default=dict)
    openrosa_headers = JSONField(default=dict)

    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    partial_submission = models.BooleanField(default=False)
    submit_ip = models.CharField(max_length=255, null=True)
    last_sync_token = models.CharField(max_length=255, null=True)
    problem = models.TextField(null=True)
    # almost always a datetime, but if it's not parseable it'll be a string
    date_header = models.DateTimeField(null=True)
    build_id = models.CharField(max_length=255, null=True)
    # export_tag = DefaultProperty(name='#export_tag')
    state = models.PositiveSmallIntegerField(choices=STATES, default=NORMAL)
    initial_processing_complete = models.BooleanField(default=False)

    deleted_on = models.DateTimeField(null=True)
    deletion_id = models.CharField(max_length=255, null=True)

    # for compatability with corehq.blobs.mixin.DeferredBlobMixin interface
    persistent_blobs = None

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
    def history(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        operations = FormAccessorSQL.get_form_operations(self.form_id) if self.is_saved() else []
        operations += self.get_tracked_models_to_create(XFormOperationSQL)
        return operations

    @property
    def metadata(self):
        from .utils import clean_metadata
        if const.TAG_META in self.form_data:
            return XFormPhoneMetadata.wrap(clean_metadata(self.form_data[const.TAG_META]))

        return None

    def soft_delete(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        FormAccessorSQL.soft_delete_forms(self.domain, [self.form_id])
        self.state |= self.DELETED

    def to_json(self, include_attachments=False):
        from .serializers import XFormInstanceSQLSerializer
        serializer = XFormInstanceSQLSerializer(self, include_attachments=include_attachments)
        data = dict(serializer.data)
        data['history'] = [dict(op) for op in data['history']]
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

        if isinstance(xml, unicode):
            xml = xml.encode('utf-8', errors='replace')

        return etree.fromstring(xml)

    def get_data(self, path):
        """
        Evaluates an xpath expression like: path/to/node and returns the value
        of that element, or None if there is no value.
        :param path: xpath like expression
        """
        return safe_index({'form': self.form_data}, path.split("/"))

    def get_xml(self):
        return self.get_attachment('form.xml')

    def xml_md5(self):
        return self.get_attachment_meta('form.xml').md5

    def archive(self, user_id=None):
        if self.is_archived:
            return
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        FormAccessorSQL.archive_form(self, user_id=user_id)
        xform_archived.send(sender="form_processor", xform=self)

    def unarchive(self, user_id=None):
        if not self.is_archived:
            return

        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        FormAccessorSQL.unarchive_form(self, user_id=user_id)
        xform_unarchived.send(sender="form_processor", xform=self)

    def __unicode__(self):
        return (
            "XFormInstance("
            "form_id='{f.form_id}', "
            "domain='{f.domain}')"
        ).format(f=self)

    class Meta:
        db_table = XFormInstanceSQL_DB_TABLE
        app_label = "form_processor"
        index_together = [
            ('domain', 'state'),
            ('domain', 'user_id'),
        ]


class AbstractAttachment(DisabledDbMixin, models.Model, SaveStateMixin):
    attachment_id = models.UUIDField(unique=True, db_index=True)
    content_type = models.CharField(max_length=255, null=True)
    content_length = models.IntegerField(null=True)
    blob_id = models.CharField(max_length=255, default=None)
    blob_bucket = models.CharField(max_length=255, null=True, default=None)

    # RFC-1864-compliant Content-MD5 header value
    md5 = models.CharField(max_length=255, default=None)

    properties = JSONField(default=dict)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.attachment_id

    def write_content(self, content):
        if not self.name:
            raise InvalidAttachment("cannot save attachment without name")

        db = get_blob_db()
        bucket = self.blobdb_bucket()
        info = db.put(content, get_short_identifier(), bucket=bucket)
        self.md5 = info.md5_hash
        self.content_length = info.length
        self.blob_id = info.identifier

    def read_content(self, stream=False):
        db = get_blob_db()
        try:
            blob = db.get(self.blob_id, self.blobdb_bucket())
        except (KeyError, NotFound, BadName):
            raise AttachmentNotFound(self.name)

        if stream:
            return blob

        with blob:
            return blob.read()

    def delete_content(self):
        db = get_blob_db()
        bucket = self.blobdb_bucket()
        deleted = db.delete(self.blob_id, bucket)
        if deleted:
            self.blob_id = None

        return deleted

    def blobdb_bucket(self):
        if self.blob_bucket is not None:
            return self.blob_bucket
        if self.attachment_id is None:
            raise AttachmentNotFound("cannot manipulate attachment on unidentified document")
        return os.path.join(self._attachment_prefix, self.attachment_id.hex)

    class Meta:
        abstract = True
        app_label = "form_processor"


class XFormAttachmentSQL(AbstractAttachment, IsImageMixin):
    objects = RestrictedManager()
    _attachment_prefix = 'form'

    name = models.CharField(max_length=255, default=None)
    form = models.ForeignKey(
        XFormInstanceSQL, to_field='form_id', db_index=False,
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment",
        on_delete=models.CASCADE,
    )

    def __unicode__(self):
        return unicode(
            "XFormAttachmentSQL("
            "attachment_id='{a.attachment_id}', "
            "form_id='{a.form_id}', "
            "name='{a.name}', "
            "content_type='{a.content_type}', "
            "content_length='{a.content_length}', "
            "md5='{a.md5}', "
            "blob_id='{a.blob_id}', "
            "properties='{a.properties}', "
        ).format(a=self)

    class Meta:
        db_table = XFormAttachmentSQL_DB_TABLE
        app_label = "form_processor"
        index_together = [
            ["form", "name"],
        ]


class XFormOperationSQL(DisabledDbMixin, models.Model):
    objects = RestrictedManager()

    ARCHIVE = 'archive'
    UNARCHIVE = 'unarchive'

    form = models.ForeignKey(XFormInstanceSQL, to_field='form_id', on_delete=models.CASCADE)
    user_id = models.CharField(max_length=255, null=True)
    operation = models.CharField(max_length=255, default=None)
    date = models.DateTimeField(auto_now_add=True)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.form, self.user_id, self.date

    @property
    def user(self):
        return self.user_id

    class Meta:
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


class CommCareCaseSQL(DisabledDbMixin, models.Model, RedisLockableMixIn,
                      AttachmentMixin, AbstractCommCareCase, TrackRelatedChanges,
                      SupplyPointCaseMixin, MessagingCaseContactMixin):
    objects = RestrictedManager()

    case_id = models.CharField(max_length=255, unique=True, db_index=True)
    domain = models.CharField(max_length=255, default=None)
    type = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True)

    owner_id = models.CharField(max_length=255, null=False)

    opened_on = models.DateTimeField(null=True)
    opened_by = models.CharField(max_length=255, null=True)

    modified_on = models.DateTimeField(null=False)
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
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        if self.is_saved():
            return CaseAccessorSQL.get_case_xform_ids(self.case_id)
        else:
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
        return OrderedDict(sorted(self.case_json.iteritems()))

    def to_api_json(self, lite=False):
        from .serializers import CommCareCaseSQLAPISerializer
        serializer = CommCareCaseSQLAPISerializer(self, lite=lite)
        return serializer.data

    def to_json(self):
        from .serializers import CommCareCaseSQLSerializer
        serializer = CommCareCaseSQLSerializer(self)
        ret = dict(serializer.data)
        ret['indices'] = [dict(index) for index in ret['indices']]
        for key in self.case_json:
            if key not in ret:
                ret[key] = self.case_json[key]
        ret['backend_id'] = 'sql'
        return ret

    def dumps(self, pretty=False):
        indent = 4 if pretty else None
        return json.dumps(self.to_json(), indent=indent)

    def pprint(self):
        print self.dumps(pretty=True)

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

        to_delete = [to_delete.identifier for to_delete in self.get_tracked_models_to_delete(CommCareCaseIndexSQL)]
        indices = [index for index in indices if index.identifier not in to_delete]

        indices += self.get_tracked_models_to_create(CommCareCaseIndexSQL)

        return indices

    @property
    def has_indices(self):
        return self.indices or self.reverse_indices

    def has_index(self, index_id):
        return index_id in (i.identifier for i in self.indices)

    def get_index(self, index_id):
        found = filter(lambda i: i.identifier == index_id, self.indices)
        if found:
            assert(len(found) == 1)
            return found[0]
        return None

    def _get_attachment_from_db(self, identifier):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_attachment_by_identifier(self.case_id, identifier)

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

    @property
    def actions(self):
        """For compatability with CommCareCase. Please use transactions when possible"""
        return self.non_revoked_transactions

    def get_transaction_by_form_id(self, form_id):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        transactions = filter(
            lambda t: t.form_id == form_id,
            self.get_tracked_models_to_create(CaseTransaction)
        )
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
        return {attachment.identifier: attachment for attachment in self.get_attachments()}

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

    def _transactions_by_type(self, transaction_type):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        if self.is_saved():
            transactions = CaseAccessorSQL.get_transactions_by_type(self.case_id, transaction_type)
        else:
            transactions = []
        transactions += filter(
            lambda t: (t.type & transaction_type) == transaction_type,
            self.get_tracked_models_to_create(CaseTransaction)
        )
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
            indices = filter(lambda index: index.identifier == identifier, indices)

        if relationship:
            indices = filter(lambda index: index.relationship_id == relationship, indices)

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

    def __unicode__(self):
        return (
            "CommCareCase("
            "case_id='{c.case_id}', "
            "domain='{c.domain}', "
            "closed={c.closed}, "
            "owner_id='{c.owner_id}', "
            "server_modified_on='{c.server_modified_on}')"
        ).format(c=self)

    class Meta:
        index_together = [
            ["domain", "owner_id", "closed"],
            ["domain", "external_id", "type"],
        ]
        app_label = "form_processor"
        db_table = CommCareCaseSQL_DB_TABLE


class CaseAttachmentSQL(AbstractAttachment, CaseAttachmentMixin):
    objects = RestrictedManager()
    _attachment_prefix = 'case'

    name = models.CharField(max_length=255, default=None)
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=False,
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment",
        on_delete=models.CASCADE,
    )
    identifier = models.CharField(max_length=255, default=None)
    attachment_src = models.TextField(null=True)
    attachment_from = models.TextField(null=True)

    def from_form_attachment(self, attachment):
        """
        Update fields in this attachment with fields from another attachment

        :param attachment: XFormAttachmentSQL or CaseAttachmentSQL object
        """
        self.content_length = attachment.content_length
        self.blob_id = attachment.blob_id
        self.blob_bucket = attachment.blobdb_bucket()
        self.md5 = attachment.md5
        self.content_type = attachment.content_type
        self.properties = attachment.properties

        if not self.content_type and self.attachment_src:
            guessed = mimetypes.guess_type(self.attachment_src)
            if len(guessed) > 0 and guessed[0] is not None:
                self.content_type = guessed[0]

        if isinstance(attachment, CaseAttachmentSQL):
            assert self.identifier == attachment.identifier
            self.attachment_src = attachment.attachment_src
            self.attachment_from = attachment.attachment_from

    @classmethod
    def from_case_update(cls, attachment):
        if attachment.attachment_src:
            ret = cls(
                attachment_id=uuid.uuid4(),
                name=attachment.attachment_name or attachment.identifier,
                identifier=attachment.identifier,
                attachment_src=attachment.attachment_src,
                attachment_from=attachment.attachment_from
            )
        else:
            ret = cls(name=attachment.identifier, identifier=attachment.identifier)
        return ret

    def __unicode__(self):
        return unicode(
            "CaseAttachmentSQL("
            "attachment_id='{a.attachment_id}', "
            "case_id='{a.case_id}', "
            "name='{a.name}', "
            "content_type='{a.content_type}', "
            "content_length='{a.content_length}', "
            "md5='{a.md5}', "
            "blob_id='{a.blob_id}', "
            "properties='{a.properties}', "
            "identifier='{a.identifier}', "
            "attachment_src='{a.attachment_src}', "
            "attachment_from='{a.attachment_from}')"
        ).format(a=self)

    class Meta:
        app_label = "form_processor"
        db_table = CaseAttachmentSQL_DB_TABLE
        index_together = [
            ["case", "identifier"],
        ]


class CommCareCaseIndexSQL(DisabledDbMixin, models.Model, SaveStateMixin):
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

    def __unicode__(self):
        return (
            "CaseIndex("
            "case_id='{i.case_id}', "
            "domain='{i.domain}', "
            "identifier='{i.identifier}', "
            "referenced_type='{i.referenced_type}', "
            "referenced_id='{i.referenced_id}', "
            "relationship='{i.relationship})"
        ).format(i=self)

    class Meta:
        index_together = [
            ["domain", "case"],
            ["domain", "referenced_id"],
        ]
        db_table = CommCareCaseIndexSQL_DB_TABLE
        app_label = "form_processor"


class CaseTransaction(DisabledDbMixin, SaveStateMixin, models.Model):
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
    TYPE_CHOICES = (
        (TYPE_FORM, 'form'),
        (TYPE_REBUILD_WITH_REASON, 'rebuild_with_reason'),
        (TYPE_REBUILD_USER_REQUESTED, 'user_requested_rebuild'),
        (TYPE_REBUILD_USER_ARCHIVED, 'user_archived_rebuild'),
        (TYPE_REBUILD_FORM_ARCHIVED, 'form_archive_rebuild'),
        (TYPE_REBUILD_FORM_EDIT, 'form_edit_rebuild'),
        (TYPE_LEDGER, 'ledger'),
        (TYPE_CASE_CREATE, 'case_create'),
        (TYPE_CASE_CLOSE, 'case_close'),
        (TYPE_CASE_ATTACHMENT, 'case_attachment'),
        (TYPE_CASE_INDEX, 'case_index'),
    )
    TYPES_TO_PROCESS = (
        TYPE_FORM,
    )
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=False,
        related_name="transaction_set", related_query_name="transaction",
        on_delete=models.CASCADE,
    )
    form_id = models.CharField(max_length=255, null=True)  # can't be a foreign key due to partitioning
    sync_log_id = models.CharField(max_length=255, null=True)
    server_date = models.DateTimeField(null=False)
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    revoked = models.BooleanField(default=False, null=False)
    details = JSONField(default=dict)

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
        return bool(
            (self.TYPE_REBUILD_FORM_ARCHIVED & self.type) or
            (self.TYPE_REBUILD_FORM_EDIT & self.type) or
            (self.TYPE_REBUILD_USER_ARCHIVED & self.type) or
            (self.TYPE_REBUILD_USER_REQUESTED & self.type) or
            (self.TYPE_REBUILD_WITH_REASON & self.type)
        )

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
    def form_transaction(cls, case, xform, action_types=None):
        action_types = action_types or []

        if any(map(lambda action_type: not cls._valid_action_type(action_type), action_types)):
            raise UnknownActionType('Unknown action type found')

        type_ = cls.TYPE_FORM

        for action_type in action_types:
            type_ |= action_type
        return cls._from_form(case, xform, transaction_type=type_)

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

    def __unicode__(self):
        return (
            "CaseTransaction("
            "case_id='{self.case_id}', "
            "form_id='{self.form_id}', "
            "sync_log_id='{self.sync_log_id}', "
            "type='{self.type}', "
            "server_date='{self.server_date}', "
            "revoked='{self.revoked}')"
        ).format(self=self)

    class Meta:
        unique_together = ("case", "form_id", "type")
        ordering = ['server_date']
        db_table = CaseTransaction_DB_TABLE
        app_label = "form_processor"
        index_together = [
            ('case', 'server_date', 'sync_log_id'),
        ]


class CaseTransactionDetail(JsonObject):
    _type = None

    @property
    def type(self):
        return self._type

    def __eq__(self, other):
        return self.type == other.type and self.to_json() == other.to_json()

    def __ne__(self, other):
        return not self.__eq__(other)


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


class LedgerValue(DisabledDbMixin, models.Model, TrackRelatedChanges):
    """
    Represents the current state of a ledger. Supercedes StockState
    """
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
    last_modified = models.DateTimeField(auto_now=True, db_index=True)
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
        try:
            return SQLLocation.objects.get(supply_point_id=self.case_id)
        except SQLLocation.DoesNotExist:
            return None

    @property
    def location_id(self):
        return self.location.location_id if self.location else None

    def to_json(self, include_location_id=True):
        from .serializers import LedgerValueSerializer
        serializer = LedgerValueSerializer(self, include_location_id=include_location_id)
        return dict(serializer.data)

    class Meta:
        app_label = "form_processor"
        db_table = LedgerValue_DB_TABLE
        unique_together = ("case", "section_id", "entry_id")


class LedgerTransaction(DisabledDbMixin, SaveStateMixin, models.Model):
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
    delta = models.IntegerField(default=0)
    # new balance
    updated_balance = models.IntegerField(default=0)

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

    def __unicode__(self):
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

    class Meta:
        db_table = LedgerTransaction_DB_TABLE
        app_label = "form_processor"
        index_together = [
            ["case", "section_id", "entry_id"],
        ]


class ConsumptionTransaction(namedtuple('ConsumptionTransaction', ['type', 'normalized_value', 'received_on'])):

    @property
    def is_stockout(self):
        from casexml.apps.stock.const import TRANSACTION_TYPE_STOCKONHAND
        return self.type == TRANSACTION_TYPE_STOCKONHAND and self.normalized_value == 0

    @property
    def is_checkpoint(self):
        from casexml.apps.stock.const import TRANSACTION_TYPE_STOCKONHAND
        return self.type == TRANSACTION_TYPE_STOCKONHAND and not self.is_stockout
