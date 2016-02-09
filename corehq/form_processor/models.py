import hashlib
import json
import os
from collections import (
    namedtuple,
    OrderedDict
)

from datetime import datetime

from StringIO import StringIO
from jsonobject import JsonObject
from jsonobject import StringProperty
from jsonobject.properties import BooleanProperty
from lxml import etree
from json_field.fields import JSONField
from django.conf import settings
from django.db import models
from uuidfield import UUIDField

from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.form_processor.track_related import TrackRelatedChanges
from corehq.sql_db.routers import db_for_read_write
from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from dimagi.ext import jsonobject
from couchforms.signals import xform_archived, xform_unarchived
from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty

from .abstract_models import AbstractXFormInstance, AbstractCommCareCase
from .exceptions import AttachmentNotFound, AccessRestricted, InvalidAttachment

XFormInstanceSQL_DB_TABLE = 'form_processor_xforminstancesql'
XFormAttachmentSQL_DB_TABLE = 'form_processor_xformattachmentsql'
XFormOperationSQL_DB_TABLE = 'form_processor_xformoperationsql'

CommCareCaseSQL_DB_TABLE = 'form_processor_commcarecasesql'
CommCareCaseIndexSQL_DB_TABLE = 'form_processor_commcarecaseindexsql'
CaseAttachmentSQL_DB_TABLE = 'form_processor_caseattachmentsql'
CaseTransaction_DB_TABLE = 'form_processor_casetransaction'


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
            content = StringIO(data.encode("utf-8"))
        elif isinstance(data, bytes):
            content = StringIO(data)
        return content

    @property
    def md5(self):
        return hashlib.md5(self.content).hexdigest()


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
    NORMAL = 0
    ARCHIVED = 1
    DEPRECATED = 2
    DUPLICATE = 4
    ERROR = 8
    SUBMISSION_ERROR_LOG = 16
    DELETED = 32
    STATES = (
        (NORMAL, 'normal'),
        (ARCHIVED, 'archived'),
        (DEPRECATED, 'deprecated'),
        (DUPLICATE, 'duplicate'),
        (ERROR, 'error'),
        (SUBMISSION_ERROR_LOG, 'submission_error'),
        (DELETED, 'deleted'),
    )

    form_id = models.CharField(max_length=255, unique=True, db_index=True)

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255, null=True)

    # When a form is deprecated, the existing form receives a new id and its original id is stored in orig_id
    orig_id = models.CharField(max_length=255, null=True)

    # When a form is deprecated, the new form gets a reference to the deprecated form
    deprecated_form_id = models.CharField(max_length=255, null=True)

    # Stores the datetime of when a form was deprecated
    edited_on = models.DateTimeField(null=True)

    # The time at which the server has received the form
    received_on = models.DateTimeField()

    # Used to tag forms that were forcefully submitted
    # without a touchforms session completing normally
    auth_context = JSONField(lazy=True, default=dict)
    openrosa_headers = JSONField(lazy=True, default=dict)
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

    @classmethod
    def get_obj_id(cls, obj):
        return obj.form_id

    @classmethod
    def get_obj_by_id(cls, form_id):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        return FormAccessorSQL.get_form(form_id)

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
        return self.state == self.DELETED

    @property
    @memoized
    def form_data(self):
        from .utils import convert_xform_to_json, adjust_datetimes
        xml = self.get_xml()
        form_json = convert_xform_to_json(xml)
        adjust_datetimes(form_json)
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
        return FormAccessorSQL.update_state(self.form_id, XFormInstanceSQL.DELETED)

    def to_json(self):
        from .serializers import XFormInstanceSQLSerializer
        serializer = XFormInstanceSQLSerializer(self)
        return serializer.data

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

        def _to_xml_element(payload):
            if isinstance(payload, unicode):
                payload = payload.encode('utf-8', errors='replace')
            return etree.fromstring(payload)
        return _to_xml_element(xml)

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


class AbstractAttachment(DisabledDbMixin, models.Model):
    attachment_id = UUIDField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    content_type = models.CharField(max_length=255)
    md5 = models.CharField(max_length=255)

    def _blobdb_bucket(self):
        if self.attachment_id is None:
            raise AttachmentNotFound(
                "cannot manipulate attachment on unidentified document")
        return os.path.join(self._attachment_prefix, str(self.attachment_id))

    def write_content(self, content):
        if not self.name:
            raise InvalidAttachment("cannot save attachment without name")

        db = get_blob_db()
        bucket = self._blobdb_bucket()
        db.put(content, self.name, bucket)

    def read_content(self):
        db = get_blob_db()
        try:
            blob = db.get(self.name, self._blobdb_bucket())
        except (KeyError, NotFound):
            raise AttachmentNotFound(u"{model} attachment: {name!r}".format(
                                   model=type(self).__name__, name=self.name))
        with blob:
            body = blob.read()
        try:
            body = body.decode("utf-8", "strict")
        except UnicodeDecodeError:
            # Return bytes on decode failure, otherwise unicode.
            # Ugly, but consistent with restkit.wrappers.Response.body_string
            pass
        return body

    def delete_content(self):
        deleted = False
        bucket = self._blobdb_bucket()
        return get_blob_db().delete(self.name, bucket) or deleted

    class Meta:
        abstract = True


class XFormAttachmentSQL(AbstractAttachment):
    objects = RestrictedManager()
    _attachment_prefix = 'form'

    form = models.ForeignKey(
        XFormInstanceSQL, to_field='form_id',
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment"
    )

    class Meta:
        db_table = XFormAttachmentSQL_DB_TABLE


class XFormOperationSQL(DisabledDbMixin, models.Model):
    objects = RestrictedManager()

    ARCHIVE = 'archive'
    UNARCHIVE = 'unarchive'

    form = models.ForeignKey(XFormInstanceSQL, to_field='form_id')
    user_id = models.CharField(max_length=255, null=True)
    operation = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    @property
    def user(self):
        return self.user_id

    class Meta:
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
        from corehq.apps.locations.models import Location
        from couchdbkit.exceptions import ResourceNotFound
        if self.location_id is None:
            return None
        try:
            return Location.get(self.location_id)
        except ResourceNotFound:
            return None

    @property
    def sql_location(self):
        from corehq.apps.locations.models import SQLLocation
        return SQLLocation.objects.get(location_id=self.location_id)


class CommCareCaseSQL(DisabledDbMixin, models.Model, RedisLockableMixIn,
                      AttachmentMixin, AbstractCommCareCase, TrackRelatedChanges,
                      SupplyPointCaseMixin):
    objects = RestrictedManager()

    case_id = models.CharField(max_length=255, unique=True, db_index=True)
    domain = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True)

    owner_id = models.CharField(max_length=255, null=False)

    opened_on = models.DateTimeField(null=True)
    opened_by = models.CharField(max_length=255, null=True)

    modified_on = models.DateTimeField(null=False)
    server_modified_on = models.DateTimeField(null=False)
    modified_by = models.CharField(max_length=255)

    closed = models.BooleanField(default=False, null=False)
    closed_on = models.DateTimeField(null=True)
    closed_by = models.CharField(max_length=255, null=True)

    deleted = models.BooleanField(default=False, null=False)

    external_id = models.CharField(max_length=255)
    location_id = models.CharField(max_length=255, null=True)

    case_json = JSONField(lazy=True, default=dict)

    @property
    def doc_type(self):
        dt = 'CommCareCase'
        if self.is_deleted:
            dt += DELETED_SUFFIX
        return dt

    @property
    def xform_ids(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_case_xform_ids(self.case_id)

    @property
    def user_id(self):
        return self.modified_by

    @user_id.setter
    def user_id(self, value):
        self.modified_by = value

    def soft_delete(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        self.deleted = True
        CaseAccessorSQL.save_case(self)

    @property
    def is_deleted(self):
        return self.deleted

    def dynamic_case_properties(self):
        return OrderedDict(sorted(self.case_json.iteritems()))

    def to_json(self):
        from .serializers import CommCareCaseSQLSerializer
        serializer = CommCareCaseSQLSerializer(self)
        return serializer.data

    def dumps(self, pretty=False):
        indent = 4 if pretty else None
        return json.dumps(self.to_json(), indent=indent)

    def pprint(self):
        print self.dumps(pretty=True)

    @property
    @memoized
    def reverse_indices(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_reverse_indices(self.case_id)

    @memoized
    def _saved_indices(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        cached_indices = 'cached_indices'
        if hasattr(self, cached_indices):
            return getattr(self, cached_indices)

        return CaseAccessorSQL.get_indices(self.case_id) if self.is_saved() else []

    @property
    def indices(self):
        indices = self._saved_indices()

        to_delete = [to_delete.identifier for to_delete in self.get_tracked_models_to_delete(CommCareCaseIndexSQL)]
        indices = [index for index in indices if index.identifier not in to_delete]

        indices += self.get_tracked_models_to_create(CommCareCaseIndexSQL)

        return indices

    def has_index(self, index_id):
            return index_id in (i.identifier for i in self.indices)

    def get_index(self, index_id):
        found = filter(lambda i: i.identifier == index_id, self.indices)
        if found:
            assert(len(found) == 1)
            return found[0]
        return None

    def _get_attachment_from_db(self, attachment_name):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_attachment_by_name(self.case_id, attachment_name)

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
    def non_revoked_transactions(self):
        return [t for t in self.transactions if not t.revoked]

    @property
    @memoized
    def case_attachments(self):
        return {attachment.name: attachment for attachment in self.get_attachments()}

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


    def on_tracked_models_cleared(self, model_class=None):
        self._saved_indices.reset_cache(self)

    @classmethod
    def get_obj_id(cls, obj):
        return obj.case_id

    @classmethod
    def get_obj_by_id(cls, case_id):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        return CaseAccessorSQL.get_case(case_id)

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
        # TODO SK 2015-11-05: verify that these are the indexes we want
        # also consider partial indexes
        index_together = [
            ["domain", "owner_id"],
            ["domain", "closed", "server_modified_on"],
        ]
        db_table = CommCareCaseSQL_DB_TABLE


class CaseAttachmentSQL(AbstractAttachment):
    objects = RestrictedManager()
    _attachment_prefix = 'case'

    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=True,
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment"
    )

    class Meta:
        db_table = CaseAttachmentSQL_DB_TABLE


class CommCareCaseIndexSQL(DisabledDbMixin, models.Model, SaveStateMixin):
    objects = RestrictedManager()

    # relationship_ids should be powers of 2
    CHILD = 0
    EXTENSION = 1
    RELATIONSHIP_CHOICES = (
        (CHILD, 'child'),
        (EXTENSION, 'extension'),
    )
    RELATIONSHIP_INVERSE_MAP = dict(RELATIONSHIP_CHOICES)
    RELATIONSHIP_MAP = {v: k for k, v in RELATIONSHIP_CHOICES}

    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=True,
        related_name="index_set", related_query_name="index"
    )
    domain = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, null=False)
    referenced_id = models.CharField(max_length=255, null=False)
    referenced_type = models.CharField(max_length=255, null=False)
    relationship_id = models.PositiveSmallIntegerField(choices=RELATIONSHIP_CHOICES)

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
            ["domain", "referenced_id"],
        ]
        db_table = CommCareCaseIndexSQL_DB_TABLE


class CaseTransaction(DisabledDbMixin, models.Model):
    objects = RestrictedManager()

    # types should be powers of 2
    TYPE_FORM = 0
    TYPE_REBUILD_WITH_REASON = 1
    TYPE_REBUILD_USER_REQUESTED = 2
    TYPE_REBUILD_USER_ARCHIVED = 4
    TYPE_REBUILD_FORM_ARCHIVED = 8
    TYPE_REBUILD_FORM_EDIT = 16
    TYPE_LEDGER = 32
    TYPE_CHOICES = (
        (TYPE_FORM, 'form'),
        (TYPE_REBUILD_WITH_REASON, 'rebuild_with_reason'),
        (TYPE_REBUILD_USER_REQUESTED, 'user_requested_rebuild'),
        (TYPE_REBUILD_USER_ARCHIVED, 'user_archived_rebuild'),
        (TYPE_REBUILD_FORM_ARCHIVED, 'form_archive_rebuild'),
        (TYPE_REBUILD_FORM_EDIT, 'form_edit_rebuild'),
        (TYPE_LEDGER, 'ledger'),
    )
    TYPES_TO_PROCESS = (
        TYPE_FORM,
    )
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_id', db_index=True,
        related_name="transaction_set", related_query_name="transaction"
    )
    form_id = models.CharField(max_length=255, null=True)  # can't be a foreign key due to partitioning
    sync_log_id = models.CharField(max_length=255, null=True)
    server_date = models.DateTimeField(null=False)
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    revoked = models.BooleanField(default=False, null=False)
    details = JSONField(lazy=True, default=dict)

    @property
    def is_relevant(self):
        relevant = not self.revoked and self.type in CaseTransaction.TYPES_TO_PROCESS
        if relevant and self.form:
            relevant = self.form.is_normal

        return relevant

    @property
    def form(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        if not self.form_id:
            return None
        form = getattr(self, 'cached_form', None)
        if not form:
            self.cached_form = FormAccessorSQL.get_form(self.form_id)
        return self.cached_form

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
    def form_transaction(cls, case, xform):
        return cls._from_form(case, xform, transaction_type=CaseTransaction.TYPE_FORM)

    @classmethod
    def ledger_transaction(cls, case, xform):
        return cls._from_form(case, xform, transaction_type=CaseTransaction.TYPE_LEDGER)

    @classmethod
    def _from_form(cls, case, xform, transaction_type):
        return CaseTransaction(
            case=case,
            form_id=xform.form_id,
            sync_log_id=xform.last_sync_token,
            server_date=xform.received_on,
            type=transaction_type,
            revoked=not xform.is_normal
        )

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
            "revoked='{self.revoked}'"
        ).format(self=self)

    class Meta:
        unique_together = ("case", "form_id")
        ordering = ['server_date']
        db_table = CaseTransaction_DB_TABLE


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


class LedgerValue(models.Model):
    """
    Represents the current state of a ledger. Supercedes StockState
    """
    # domain not included and assumed to be accessed through the foreign key to the case table. legit?
    case_id = models.CharField(max_length=255, db_index=True)  # remove foreign key until we're sharding this
    # can't be a foreign key to products because of sharding.
    # also still unclear whether we plan to support ledgers to non-products
    entry_id = models.CharField(max_length=100, db_index=True)
    section_id = models.CharField(max_length=100, db_index=True)
    balance = models.IntegerField(default=0)  # todo: confirm we aren't ever intending to support decimals
    last_modified = models.DateTimeField(auto_now=True)

CaseAction = namedtuple("CaseAction", ["action_type", "updated_known_properties", "indices"])
