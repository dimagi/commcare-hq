import hashlib
import json
import os
import collections

from datetime import datetime
from django.db.models import Prefetch
from jsonobject import JsonObject
from jsonobject import StringProperty
from jsonobject.properties import BooleanProperty
from lxml import etree
from json_field.fields import JSONField
from django.conf import settings
from django.db import models, transaction
from uuidfield import UUIDField

from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.track_related import TrackRelatedChanges

from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.decorators.memoized import memoized
from dimagi.ext import jsonobject
from couchforms.signals import xform_archived, xform_unarchived
from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty

from .abstract_models import AbstractXFormInstance, AbstractCommCareCase
from .exceptions import XFormNotFound, AttachmentNotFound


class Attachment(collections.namedtuple('Attachment', 'name raw_content content_type')):
    @property
    @memoized
    def content(self):
        if hasattr(self.raw_content, 'read'):
            if hasattr(self.raw_content, 'seek'):
                self.raw_content.seek(0)
            data = self.raw_content.read()
        else:
            data = self.raw_content
        return data

    @property
    def md5(self):
        return hashlib.md5(self.content).hexdigest()


class PreSaveHashableMixin(object):
    hash_property = None

    def __hash__(self):
        hash_val = getattr(self, self.hash_property, None)
        if not hash_val:
            raise TypeError("Form instances without form ID value are unhashable")
        return hash(hash_val)


class SaveStateMixin(object):
    def is_saved(self):
        return bool(self._get_pk_val())


class AttachmentMixin(SaveStateMixin):
    """Requires the model to be linked to the attachments model via the 'attachments' related name.
    """
    ATTACHMENTS_RELATED_NAME = 'attachments'

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
            return self.attachments.filter(name=attachment_name).first()


class XFormInstanceSQL(PreSaveHashableMixin, models.Model, RedisLockableMixIn, AttachmentMixin, AbstractXFormInstance):
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

    hash_property = 'form_uuid'

    form_uuid = models.CharField(max_length=255, unique=True, db_index=True)

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

    @property
    def form_id(self):
        return self.form_uuid

    @form_id.setter
    def form_id(self, _id):
        self.form_uuid = _id

    @classmethod
    def get(cls, xform_id):
        try:
            return XFormInstanceSQL.objects.get(form_uuid=xform_id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @classmethod
    def get_with_attachments(cls, xform_id):
        try:
            return XFormInstanceSQL.objects.prefetch_related(
                Prefetch('attachments', to_attr='cached_attachments')
            ).get(form_uuid=xform_id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @classmethod
    def get_forms_with_attachments(cls, xform_ids):
        return XFormInstanceSQL.objects.prefetch_related(
            Prefetch('attachments', to_attr='cached_attachments')
        ).filter(form_uuid__in=xform_ids)

    @classmethod
    def get_obj_id(cls, obj):
        return obj.form_uuid

    @classmethod
    def get_obj_by_id(cls, _id):
        return cls.get(_id)

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
        from .utils import convert_xform_to_json, adjust_datetimes
        xml = self.get_xml()
        form_json = convert_xform_to_json(xml)
        adjust_datetimes(form_json)
        return form_json

    @property
    def history(self):
        return self.xformoperationsql_set.order_by('date')

    @property
    def metadata(self):
        from .utils import clean_metadata
        if const.TAG_META in self.form_data:
            return XFormPhoneMetadata.wrap(clean_metadata(self.form_data[const.TAG_META]))

        return None

    def to_json(self):
        from .serializers import XFormInstanceSQLSerializer
        serializer = XFormInstanceSQLSerializer(self)
        return serializer.data

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
        """
        return safe_index({'form': self.form_data}, path.split("/"))

    def get_xml(self):
        return self.get_attachment('form.xml')

    def xml_md5(self):
        return self.get_attachment_meta('form.xml').md5

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
            CaseTransaction.objects.filter(form_uuid=self.form_id).update(revoked=True)
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
            CaseTransaction.objects.filter(form_uuid=self.form_id).update(revoked=False)
        xform_unarchived.send(sender="form_processor", xform=self)


class AbstractAttachment(models.Model):
    attachment_uuid = models.CharField(max_length=255, unique=True, db_index=True)
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

    class Meta:
        abstract = True


class XFormAttachmentSQL(AbstractAttachment):
    xform = models.ForeignKey(
        XFormInstanceSQL, to_field='form_uuid', db_column='form_uuid',
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment"
    )


class XFormOperationSQL(models.Model):
    ARCHIVE = 'archive'
    UNARCHIVE = 'unarchive'

    user = models.CharField(max_length=255, null=True)
    operation = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    xform = models.ForeignKey(XFormInstanceSQL, to_field='form_uuid')


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


class CommCareCaseSQL(PreSaveHashableMixin, models.Model, RedisLockableMixIn,
                      AttachmentMixin, AbstractCommCareCase, TrackRelatedChanges,
                      SupplyPointCaseMixin):
    hash_property = 'case_uuid'

    case_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    domain = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    name = models.CharField(max_length=255, null=True)

    owner_id = models.CharField(max_length=255)

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
    location_uuid = UUIDField(null=True, unique=False)

    case_json = JSONField(lazy=True, default=dict)

    @property
    def case_id(self):
        return self.case_uuid

    @case_id.setter
    def case_id(self, _id):
        self.case_uuid = _id

    @property
    def location_id(self):
        return str(self.location_uuid)

    @location_id.setter
    def location_id(self, _id):
        self.location_uuid = _id

    @property
    def xform_ids(self):
        return list(self.transaction_set.filter(
            revoked=False,
            form_uuid__isnull=False,
            type=CaseTransaction.TYPE_FORM
        ).values_list('form_uuid', flat=True))

    @property
    def user_id(self):
        return self.modified_by

    @user_id.setter
    def user_id(self, value):
        self.modified_by = value

    def soft_delete(self):
        self.deleted = True
        self.save()

    @property
    def is_deleted(self):
        return self.deleted

    def dynamic_case_properties(self):
        return self.case_json

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
        return list(CommCareCaseIndexSQL.objects.filter(referenced_id=self.case_id).all())

    @memoized
    def _saved_indices(self):
        return self.index_set.all() if self.is_saved() else []

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

    @property
    @memoized
    def transactions(self):
        return list(self.transaction_set.all())

    @memoized
    def _saved_attachments(self):
        return self.attachments.all()

    @property
    def case_attachments(self):
        return {attachment.name: attachment for attachment in self._saved_attachments()}

    def on_tracked_models_cleared(self, model_class=None):
        self._saved_indices.reset_cache(self)

    @classmethod
    def get(cls, case_id):
        try:
            return CommCareCaseSQL.objects.get(case_uuid=case_id)
        except CommCareCaseSQL.DoesNotExist:
            raise CaseNotFound

    @classmethod
    def get_cases(cls, ids, ordered=False):
        cases = CommCareCaseSQL.objects.filter(case_uuid__in=list(ids))
        if ordered:
            # SQL won't return the rows in any particular order so we need to order them ourselves
            index_map = {id_: index for index, id_ in enumerate(ids)}
            ordered_cases = [None] * len(ids)
            for case in cases:
                ordered_cases[index_map[case.case_id]] = case

            cases = ordered_cases

        return cases

    @classmethod
    def get_case_xform_ids(cls, case_id):
        return CaseTransaction.objects.filter(case_id=case_id).values_list('form_uuid', flat=True)

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


class CaseAttachmentSQL(AbstractAttachment):
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=True,
        related_name=AttachmentMixin.ATTACHMENTS_RELATED_NAME, related_query_name="attachment"
    )


class CommCareCaseIndexSQL(models.Model, SaveStateMixin):
    CHILD = 0
    EXTENSION = 1
    RELATIONSHIP_CHOICES = (
        (CHILD, 'child'),
        (EXTENSION, 'extension'),
    )
    RELATIONSHIP_INVERSE_MAP = dict(RELATIONSHIP_CHOICES)
    RELATIONSHIP_MAP = {v: k for k, v in RELATIONSHIP_CHOICES}

    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=True,
        related_name="index_set", related_query_name="index"
    )
    domain = models.CharField(max_length=255)  # TODO SK 2015-11-05: is this necessary or should we join on case?
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


class CaseTransaction(models.Model):
    TYPE_FORM = 0
    TYPE_REBUILD_WITH_REASON = 1
    TYPE_REBUILD_USER_REQUESTED = 2
    TYPE_REBUILD_USER_ARCHIVED = 3
    TYPE_REBUILD_FORM_ARCHIVED = 4
    TYPE_REBUILD_FORM_EDIT = 5
    TYPE_CHOICES = (
        (TYPE_FORM, 'form'),
        (TYPE_REBUILD_WITH_REASON, 'rebuild_with_reason'),
        (TYPE_REBUILD_USER_REQUESTED, 'user_requested_rebuild'),
        (TYPE_REBUILD_USER_ARCHIVED, 'user_archived_rebuild'),
        (TYPE_REBUILD_FORM_ARCHIVED, 'form_archive_rebuild'),
        (TYPE_REBUILD_FORM_EDIT, 'form_edit_rebuild'),
    )
    TYPES_TO_PROCESS = (
        TYPE_FORM,
    )
    case = models.ForeignKey(
        'CommCareCaseSQL', to_field='case_uuid', db_column='case_uuid', db_index=False,
        related_name="transaction_set", related_query_name="transaction"
    )
    form_uuid = models.CharField(max_length=255, null=True)  # can't be a foreign key due to partitioning
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
        if not self.form_uuid:
            return None
        form = getattr(self, 'cached_form', None)
        if not form:
            self.cached_form = XFormAttachmentSQL.objects.get(self.form_uuid)
        return self.cached_form

    def __eq__(self, other):
        if not isinstance(other, CaseTransaction):
            return False

        return (
            self.case_id == other.case_id and
            self.type == other.type and
            self.form_uuid == other.form_uuid
        )

    def __ne__(self, other):
        return not self.__eq__(other)


    @classmethod
    def form_transaction(cls, case, xform):
        return CaseTransaction(
            case=case,
            form_uuid=xform.form_id,
            server_date=xform.received_on,
            type=CaseTransaction.TYPE_FORM,
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

    @classmethod
    def get_transactions_for_case_rebuild(cls, case_id):
        return list(CaseTransaction.objects.filter(
            case_id=case_id,
            revoked=False,
            type__in=CaseTransaction.TYPES_TO_PROCESS
        ).all())

    def __unicode__(self):
        return (
            "CaseTransaction("
            "case_id='{self.case_id}', "
            "form_id='{self.form_uuid}', "
            "type='{self.type}', "
            "server_date='{self.server_date}', "
            "revoked='{self.revoked}'"
        ).format(self=self)

    class Meta:
        unique_together = ("case", "form_uuid")
        ordering = ['server_date']


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
