import logging

from django.db import InternalError, models, transaction
from django.db.models import Q

from jsonfield.fields import JSONField
from lxml import etree
from memoized import memoized

from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty
from dimagi.ext import jsonobject
from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.sql_db.models import PartitionedModel, RequireDBManager
from corehq.sql_db.util import paginate_query_across_partitioned_databases

from ..exceptions import (
    AttachmentNotFound,
    MissingFormXml,
    XFormNotFound,
    XFormSaveError,
)
from ..track_related import TrackRelatedChanges
from .abstract import AbstractXFormInstance
from .attachment import AttachmentMixin
from .mixin import SaveStateMixin
from .util import sort_with_id_list

log = logging.getLogger(__name__)


class XFormInstanceManager(RequireDBManager):

    def get_form(self, form_id, domain=None):
        """Get form in domain

        This will get a form from any domain if the domain is not provided,
        but a domain should be provided if possible to prevent getting
        a form from the wrong domain.
        """
        try:
            kwargs = {'form_id': form_id}
            if domain is not None:
                kwargs['domain'] = domain
            return self.partitioned_get(form_id, **kwargs)
        except self.model.DoesNotExist:
            raise XFormNotFound(form_id)

    def get_forms(self, form_ids, domain=None, ordered=False):
        """
        :param form_ids: list of form_ids to fetch
        :param domain: Currently unused, may be enforced in the future.
        :param ordered:  True if the list of returned forms should have the
                         same order as the list of form_ids passed in
        """
        assert isinstance(form_ids, list)
        if not form_ids:
            return []
        forms = list(self.plproxy_raw('SELECT * from get_forms_by_id(%s)', [form_ids]))
        if ordered:
            sort_with_id_list(forms, form_ids, 'form_id')
        return forms

    @staticmethod
    def get_attachments(form_id):
        return get_blob_db().metadb.get_for_parent(form_id)

    def iter_form_ids_by_xmlns(self, domain, xmlns=None):
        q_expr = Q(domain=domain) & Q(state=self.model.NORMAL)
        if xmlns:
            q_expr &= Q(xmlns=xmlns)
        for form_id in paginate_query_across_partitioned_databases(
                self.model, q_expr, values=['form_id'], load_source='formids_by_xmlns'):
            yield form_id[0]

    @staticmethod
    def save_new_form(form):
        """Save a previously unsaved form"""
        if form.is_saved():
            raise XFormSaveError('form already saved')
        log.debug('Saving new form: %s', form)

        operations = form.get_tracked_models_to_create(XFormOperation)
        for operation in operations:
            if operation.is_saved():
                raise XFormSaveError(f'XFormOperation {operation.id} has already been saved')
            operation.form_id = form.form_id

        try:
            with form.attachment_writer() as attachment_writer, \
                    transaction.atomic(using=form.db, savepoint=False):
                transaction.on_commit(attachment_writer.commit, using=form.db)
                form.save()
                attachment_writer.write()
                for operation in operations:
                    operation.save()
        except InternalError as e:
            raise XFormSaveError(e)

        form.clear_tracked_models()


class XFormInstance(PartitionedModel, models.Model, RedisLockableMixIn, AttachmentMixin,
                    AbstractXFormInstance, TrackRelatedChanges):
    partition_attr = 'form_id'

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
    DOC_TYPE_TO_STATE = {
        "XFormInstance": NORMAL,
        "XFormError": ERROR,
        "XFormDuplicate": DUPLICATE,
        "XFormDeprecated": DEPRECATED,
        "XFormArchived": ARCHIVED,
        "SubmissionErrorLog": SUBMISSION_ERROR_LOG
    }
    ALL_DOC_TYPES = {'XFormInstance-Deleted'} | DOC_TYPE_TO_STATE.keys()
    STATE_TO_DOC_TYPE = {v: k for k, v in DOC_TYPE_TO_STATE.items()}

    objects = XFormInstanceManager()

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
        super(XFormInstance, self).__init__(*args, **kwargs)
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
        return cls.objects.get_form(form_id)

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
        if self.is_deleted:
            return 'XFormInstance' + DELETED_SUFFIX
        return self.STATE_TO_DOC_TYPE.get(self.state, 'XFormInstance')

    @property
    @memoized
    def attachments(self):
        from couchforms.const import ATTACHMENT_NAME
        return {att.name: att for att in self.get_attachments() if att.name != ATTACHMENT_NAME}

    @property
    @memoized
    def serialized_attachments(self):
        from ..serializers import XFormAttachmentSQLSerializer
        return {
            att.name: XFormAttachmentSQLSerializer(att).data
            for att in self.get_attachments()
        }

    @property
    @memoized
    def form_data(self):
        """Returns the JSON representation of the form XML"""
        from couchforms import XMLSyntaxError
        from ..utils import convert_xform_to_json, adjust_datetimes
        from corehq.form_processor.utils.metadata import scrub_form_meta
        xml = self.get_xml()
        try:
            form_json = convert_xform_to_json(xml)
        except XMLSyntaxError:
            return {}
        adjust_datetimes(form_json)

        scrub_form_meta(self.form_id, form_json)
        return form_json

    @property
    @memoized
    def history(self):
        """:returns: List of XFormOperation objects"""
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        operations = FormAccessorSQL.get_form_operations(self.form_id) if self.is_saved() else []
        operations += self.get_tracked_models_to_create(XFormOperation)
        return operations

    @property
    def metadata(self):
        from ..utils import clean_metadata
        if const.TAG_META in self.form_data:
            return XFormPhoneMetadata.wrap(clean_metadata(self.form_data[const.TAG_META]))

    def soft_delete(self):
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        FormAccessorSQL.soft_delete_forms(self.domain, [self.form_id])
        self.state |= self.DELETED

    def to_json(self, include_attachments=False):
        from ..serializers import XFormInstanceSerializer, lazy_serialize_form_attachments, \
            lazy_serialize_form_history
        serializer = XFormInstanceSerializer(self)
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
        return type(self).objects.get_attachments(self.form_id)

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
        try:
            return self.get_attachment('form.xml')
        except (NotFound, AttachmentNotFound):
            raise MissingFormXml(self.form_id)

    def xml_md5(self):
        try:
            return self.get_attachment_meta('form.xml').content_md5()
        except (NotFound, AttachmentNotFound):
            raise MissingFormXml(self.form_id)

    def archive(self, user_id=None, trigger_signals=True):
        from ..interfaces.dbaccessors import FormAccessors
        if not self.is_archived:
            FormAccessors.do_archive(self, True, user_id, trigger_signals)

    def unarchive(self, user_id=None, trigger_signals=True):
        from ..interfaces.dbaccessors import FormAccessors
        if self.is_archived:
            FormAccessors.do_archive(self, False, user_id, trigger_signals)

    def __str__(self):
        return (
            "{f.doc_type}("
            "form_id='{f.form_id}', "
            "domain='{f.domain}', "
            "xmlns='{f.xmlns}', "
            ")"
        ).format(f=self)

    class Meta(object):
        db_table = "form_processor_xforminstancesql"
        app_label = "form_processor"
        index_together = [
            ('domain', 'state'),
            ('domain', 'user_id'),
        ]
        indexes = [
            models.Index(fields=['xmlns'])
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


class XFormOperation(PartitionedModel, SaveStateMixin, models.Model):
    partition_attr = 'form_id'

    ARCHIVE = 'archive'
    UNARCHIVE = 'unarchive'
    EDIT = 'edit'
    UUID_DATA_FIX = 'uuid_data_fix'
    GDPR_SCRUB = 'gdpr_scrub'

    form = models.ForeignKey(XFormInstance, to_field='form_id', on_delete=models.CASCADE)
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
        db_table = "form_processor_xformoperationsql"


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
