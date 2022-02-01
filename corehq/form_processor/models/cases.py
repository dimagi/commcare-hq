import functools
import json
import mimetypes
import os
import uuid
from collections import OrderedDict, namedtuple
from datetime import datetime

from django.db import models

from jsonfield.fields import JSONField
from jsonobject import JsonObject, StringProperty
from jsonobject.properties import BooleanProperty
from memoized import memoized

from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.sms.mixin import MessagingCaseContactMixin
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.exceptions import BadName, NotFound
from corehq.blobs.util import get_content_md5
from corehq.sql_db.models import PartitionedModel, RequireDBManager
from corehq.util.json import CommCareJSONEncoder

from ..exceptions import AttachmentNotFound, CaseNotFound, UnknownActionType
from ..track_related import TrackRelatedChanges
from .attachment import AttachmentMixin
from .forms import XFormInstance
from .mixin import CaseToXMLMixin, IsImageMixin, SaveStateMixin

DEFAULT_PARENT_IDENTIFIER = 'parent'

CaseAction = namedtuple("CaseAction", ["action_type", "updated_known_properties", "indices"])


class CommCareCaseManager(RequireDBManager):

    def get_case(self, case_id, domain=None):
        if not case_id:
            raise CaseNotFound(case_id)
        kwargs = {"case_id": case_id}
        if domain is not None:
            kwargs["domain"] = domain
        try:
            return self.partitioned_get(case_id, **kwargs)
        except CommCareCase.DoesNotExist:
            raise CaseNotFound(case_id)


class CommCareCase(PartitionedModel, models.Model, RedisLockableMixIn,
                   AttachmentMixin, CaseToXMLMixin, TrackRelatedChanges,
                   MessagingCaseContactMixin):
    DOC_TYPE = 'CommCareCase'
    partition_attr = 'case_id'
    objects = CommCareCaseManager()

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

    def __init__(self, *args, **kwargs):
        if "indices" in kwargs:
            self._set_indices(kwargs.pop("indices"))
        super().__init__(*args, **kwargs)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.case_id

    @property
    def doc_type(self):
        dt = self.DOC_TYPE
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
    @memoized
    def location(self):
        """Get supply point location or `None` if it does not exist."""
        from corehq.apps.locations.models import SQLLocation
        if self.location_id is None:
            return None
        try:
            return self.sql_location
        except SQLLocation.DoesNotExist:
            return None

    @property
    def sql_location(self):
        """Get supply point location

        Raises `SQLLocation.DoesNotExist` if not found.
        """
        from corehq.apps.locations.models import SQLLocation
        return SQLLocation.objects.get(location_id=self.location_id)

    @property
    def user_id(self):
        return self.modified_by

    @user_id.setter
    def user_id(self, value):
        self.modified_by = value

    @property
    def is_deleted(self):
        return self.deleted

    def dynamic_case_properties(self):
        return OrderedDict(sorted(self.case_json.items()))

    def get_properties_in_api_format(self):
        return {
            **self.case_json,
            "external_id": self.external_id,
            "owner_id": self.owner_id,
            "case_name": self.name,  # renamed
            "case_type": self.type,  # renamed
            "date_opened": self.opened_on,
        }

    def to_api_json(self, lite=False):
        from ..serializers import CommCareCaseAPISerializer
        serializer = CommCareCaseAPISerializer(self, lite=lite)
        return serializer.data

    def to_json(self):
        from ..serializers import (
            CommCareCaseSerializer,
            lazy_serialize_case_attachments,
            lazy_serialize_case_indices,
            lazy_serialize_case_transactions,
            lazy_serialize_case_xform_ids,
        )
        serializer = CommCareCaseSerializer(self)
        return {
            **self.case_json,
            **serializer.data,
            'indices': lazy_serialize_case_indices(self),
            'actions': lazy_serialize_case_transactions(self),
            'xform_ids': lazy_serialize_case_xform_ids(self),
            'case_attachments': lazy_serialize_case_attachments(self),
            'backend_id': 'sql',
        }

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

    def _set_indices(self, value):
        """Set previously-saved indices

        Private setter used by the class constructor to populate indices
        from a source such as ElasticSearch. This setter does not update
        tracked models, and therefore is not intended for use with cases
        whose state is being mutated.

        :param value: A list of dicts that will be used to construct
        `CommCareCaseIndex` objects.
        """
        self.cached_indices = [CommCareCaseIndex(**x) for x in value]

    @property
    def indices(self):
        indices = self._saved_indices()

        to_delete = [
            (to_delete.id, to_delete.identifier)
            for to_delete in self.get_tracked_models_to_delete(CommCareCaseIndex)
        ]
        indices = [index for index in indices if (index.id, index.identifier) not in to_delete]

        indices += self.get_tracked_models_to_create(CommCareCaseIndex)

        return indices

    @property
    def live_indices(self):
        return [i for i in self.indices if not i.is_deleted]

    @property
    def has_indices(self):
        return self.live_indices or self.reverse_indices

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
        """DEPRECATED use transactions instead"""
        return self.non_revoked_transactions

    def _get_unsaved_transaction_for_form(self, form_id):
        transactions = [t for t in self.get_tracked_models_to_create(CaseTransaction) if t.form_id == form_id]
        assert len(transactions) <= 1
        return transactions[0] if transactions else None

    def get_transaction_by_form_id(self, form_id):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        transaction = self._get_unsaved_transaction_for_form(form_id)

        if not transaction and self.is_saved():
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
        from ..serializers import CaseAttachmentSerializer
        return {
            att.name: dict(CaseAttachmentSerializer(att).data)
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
        transactions += [
            t for t in self.get_tracked_models_to_create(CaseTransaction)
            if (t.type & transaction_type) == transaction_type
        ]
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

    def get_case_property(self, property, dynamic_only=False):
        if property in self.case_json:
            return self.case_json[property]

        if dynamic_only:
            return

        allowed_fields = [
            field.name for field in self._meta.fields
            if field.name not in ('id', 'case_json')
        ]
        if property in allowed_fields:
            return getattr(self, property)

    def on_tracked_models_cleared(self, model_class=None):
        self._saved_indices.reset_cache(self)

    def resolve_case_property(self, property_name):
        """
        Takes a case property expression and resolves the necessary references
        to get the case property value(s).

        property_name - The case property expression. Examples: name, parent/name,
                        parent/parent/name

        Returns a list of named tuples of (case, value), where value is the
        resolved case property value and case is the case that yielded that value.
        There can be more than one tuple in the returned result if a case has more
        than one parent or grandparent.
        """
        result = []
        self._resolve_case_property(property_name, result)
        return result

    def _resolve_case_property(self, property_name, result):
        CasePropertyResult = namedtuple('CasePropertyResult', 'case value')

        if property_name.lower().startswith('parent/'):
            parents = self.get_parent(identifier=DEFAULT_PARENT_IDENTIFIER)
            for parent in parents:
                parent._resolve_case_property(property_name[7:], result)
            return

        if property_name.lower().startswith('host/'):
            host = self.host
            if host:
                host._resolve_case_property(property_name[5:], result)
            return

        if property_name == '_id':
            property_name = 'case_id'

        result.append(CasePropertyResult(
            self,
            self.get_case_property(property_name)
        ))

    @memoized
    def get_index_map(self, reversed=False):
        indices = self.indices if not reversed else self.reverse_indices
        return get_index_map(indices)

    @memoized
    def get_attachment_map(self):
        return {
            name: {
                'url': self.get_attachment_server_url(att.identifier),
                'content_type': att.content_type,
            }
            for name, att in self.case_attachments.items()
        }

    def to_xml(self, version, include_case_on_closed=False):
        from lxml import etree as ElementTree
        from casexml.apps.phone.xml import get_case_element
        if self.closed:
            if include_case_on_closed:
                elem = get_case_element(self, ('create', 'update', 'close'), version)
            else:
                elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem, encoding='utf-8')

    def get_attachment_server_url(self, name):
        """
        A server specific URL for remote clients to access case attachment resources async.
        """
        if name in self.case_attachments:
            from dimagi.utils import web
            from django.urls import reverse
            return "%s%s" % (
                web.get_url_base(),
                reverse("api_case_attachment", kwargs={
                    "domain": self.domain,
                    "case_id": self.case_id,
                    "attachment_id": name,
                }),
            )
        return None

    @classmethod
    def get_obj_id(cls, obj):
        return obj.case_id

    @classmethod
    def get_obj_by_id(cls, case_id):
        return cls.objects.get_case(case_id)

    @memoized
    def get_parent(self, identifier=None, relationship=None):
        indices = self.indices

        if identifier:
            indices = [index for index in indices if index.identifier == identifier]

        if relationship:
            indices = [index for index in indices if index.relationship_id == relationship]

        return [index.referenced_case for index in indices if index.referenced_id]

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
            relationship=CommCareCaseIndex.CHILD
        )
        return result[0] if result else None

    @property
    def host(self):
        result = self.get_parent(relationship=CommCareCaseIndex.EXTENSION)
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
        db_table = 'form_processor_commcarecasesql'


def get_index_map(indices):
    return dict([
        (index.identifier, {
            "case_type": index.referenced_type,
            "case_id": index.referenced_id,
            "relationship": index.relationship,
        }) for index in indices
    ])


class CaseAttachment(PartitionedModel, models.Model, SaveStateMixin, IsImageMixin):
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

    case = models.ForeignKey(
        'CommCareCase', to_field='case_id', db_index=False,
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

    # DEPRECATED - use CaseAttachment.content_md5() instead
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
                raise AttachmentNotFound(self.case_id, self.name)
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
        return str(
            "CaseAttachment("
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
            return get_blob_db().get(key=self.key, type_code=CODES.form_attachment)
        except (KeyError, NotFound, BadName):
            raise AttachmentNotFound(self.case_id, self.name)

    @memoized
    def content_md5(self):
        """Get RFC-1864-compliant Content-MD5 header value"""
        with self.open() as fileobj:
            return get_content_md5(fileobj)

    class Meta(object):
        app_label = "form_processor"
        db_table = "form_processor_caseattachmentsql"
        index_together = [
            ["case", "name"],
        ]


class CommCareCaseIndex(PartitionedModel, models.Model, SaveStateMixin):
    partition_attr = 'case_id'

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
        'CommCareCase', to_field='case_id', db_index=False,
        related_name="index_set", related_query_name="index",
        on_delete=models.CASCADE,
    )
    domain = models.CharField(max_length=255, default=None)
    identifier = models.CharField(max_length=255, default=None)
    referenced_id = models.CharField(max_length=255, default=None)
    referenced_type = models.CharField(max_length=255, default=None)
    relationship_id = models.PositiveSmallIntegerField(choices=RELATIONSHIP_CHOICES)

    def __init__(self, *args, **kwargs):
        # HACK: We need to remove doc_type, as ElasticSearch queries write the entire
        #  couch document to ElasticSearch, and these indices are typically constructed by
        #  passing the entire raw elasticsearch doc to this constructor.
        #  While this could be handled during the parsing phase, we have multiple unique
        #  paths which both parse, so we'd need to ignore doc_type in multiple places
        #  Ideally, this fix can be removed when 'doc_type' is no longer written to ElasticSearch
        #  and existing docs have been re-saved.
        kwargs.pop('doc_type', None)
        super().__init__(*args, **kwargs)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.domain, self.case, self.identifier

    @property
    def is_deleted(self):
        return not self.referenced_id

    @property
    @memoized
    def referenced_case(self):
        """
        For a 'forward' index this is the case that the the index points to.
        For a 'reverse' index this is the case that owns the index.
        See ``CaseAccessorSQL.get_reverse_indices``

        :return: referenced case
        """
        if self.referenced_id:
            return CommCareCase.objects.get_case(self.referenced_id, self.domain)
        else:
            return None

    @property
    def relationship(self):
        return self.RELATIONSHIP_INVERSE_MAP[self.relationship_id]

    @relationship.setter
    def relationship(self, relationship):
        self.relationship_id = self.RELATIONSHIP_MAP[relationship]

    def __eq__(self, other):
        return isinstance(other, CommCareCaseIndex) and (
            self.case_id == other.case_id
            and self.identifier == other.identifier
            and self.referenced_id == other.referenced_id
            and self.referenced_type == other.referenced_type
            and self.relationship_id == other.relationship_id
        )

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
        db_table = 'form_processor_commcarecaseindexsql'
        app_label = "form_processor"


class CaseTransaction(PartitionedModel, SaveStateMixin, models.Model):
    partition_attr = 'case_id'

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
        'CommCareCase', to_field='case_id', db_index=False,
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
        if not self.form_id:
            return None
        form = getattr(self, 'cached_form', None)
        if not form:
            self.cached_form = XFormInstance.objects.get_form(self.form_id)
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

    @property
    def xmlns(self):
        return self.details.get('xmlns', None) if self.details else None

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
            self.case_id == other.case_id
            and self.type == other.type
            and self.form_id == other.form_id
        )

    def __hash__(self):
        return hash((self.case_id, self.type, self.form_id))

    @classmethod
    def form_transaction(cls, case, xform, client_date, action_types=None):
        """Get or create a form transaction for a the given form and case.
        """
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
        """Get or create a ledger transaction for a the given form and case.
        """
        return cls._from_form(
            case,
            xform,
            transaction_type=CaseTransaction.TYPE_LEDGER | CaseTransaction.TYPE_FORM
        )

    @classmethod
    def _from_form(cls, case, xform, transaction_type):
        if xform.is_saved():
            transaction = case.get_transaction_by_form_id(xform.form_id)
        else:
            transaction = case._get_unsaved_transaction_for_form(xform.form_id)
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
                revoked=not xform.is_normal,
                details=FormSubmissionDetail(xmlns=xform.xmlns).to_json()
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
        db_table = 'form_processor_casetransaction'
        app_label = "form_processor"
        index_together = [
            ('case', 'server_date', 'sync_log_id'),
        ]
        indexes = [models.Index(fields=['form_id'])]


class CaseTransactionDetail(JsonObject):
    _type = None

    @property
    def type(self):
        return self._type

    def __eq__(self, other):
        return self.type == other.type and self.to_json() == other.to_json()

    __hash__ = None


class FormSubmissionDetail(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_FORM
    xmlns = StringProperty()


class RebuildWithReason(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_WITH_REASON
    reason = StringProperty()


class UserRequestedRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_USER_REQUESTED
    user_id = StringProperty()


class UserArchivedRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_USER_ARCHIVED
    user_id = StringProperty()


class FormArchiveRebuild(FormSubmissionDetail):
    _type = CaseTransaction.TYPE_REBUILD_FORM_ARCHIVED
    form_id = StringProperty()
    archived = BooleanProperty()


class FormEditRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_FORM_EDIT
    deprecated_form_id = StringProperty()


class FormReprocessRebuild(CaseTransactionDetail):
    _type = CaseTransaction.TYPE_REBUILD_FORM_REPROCESS
    form_id = StringProperty()
