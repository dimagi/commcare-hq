import logging
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.db import InternalError, models, transaction
from django.db.models import Q

from jsonfield.fields import JSONField
from lxml import etree
from memoized import memoized

from couchforms import const
from couchforms.jsonobject_extensions import GeoPointProperty
from couchforms.signals import xform_archived, xform_unarchived
from dimagi.ext import jsonobject
from dimagi.utils.chunked import chunked
from dimagi.utils.couch import RedisLockableMixIn
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.cleanup.models import create_deleted_sql_doc, DeletedSQLDoc
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.blobs.exceptions import NotFound
from corehq.sql_db.models import PartitionedModel, RequireDBManager
from corehq.sql_db.util import (
    create_unique_index_name,
    get_db_alias_for_partitioned_doc,
    get_db_aliases_for_partitioned_query,
    paginate_query_across_partitioned_databases,
    split_list_by_db_partition,
)

from ..exceptions import (
    AttachmentNotFound,
    MissingFormXml,
    XFormNotFound,
    XFormSaveError,
)
from ..submission_process_tracker import unfinished_archive
from ..system_action import system_action
from ..track_related import TrackRelatedChanges
from .attachment import AttachmentContent, AttachmentMixin
from .mixin import SaveStateMixin
from .util import attach_prefetch_models, fetchall_as_namedtuple, sort_with_id_list

log = logging.getLogger(__name__)

ARCHIVE_FORM = "archive_form"


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

    def form_exists(self, form_id, domain=None):
        query = self.partitioned_query(form_id).filter(form_id=form_id)
        if domain:
            query = query.filter(domain=domain)
        return query.exists()

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

    def iter_forms(self, form_ids, domain=None):
        """
        :param form_ids: list of form_ids.
        :param domain: See the same parameter of `get_forms`.
        """
        for chunk in chunked(form_ids, 100):
            yield from self.get_forms([_f for _f in chunk if _f], domain)

    @staticmethod
    def get_attachments(form_id):
        return get_blob_db().metadb.get_for_parent(form_id)

    def get_with_attachments(self, form_id, domain=None):
        """
        It's necessary to store these on the form rather than use a memoized property
        since the form_id can change (in the case of a deprecated form) which breaks
        the memoize hash.
        """
        form = self.get_form(form_id, domain)
        form.attachments_list = self.get_attachments(form_id)
        return form

    def get_attachment_by_name(self, form_id, attachment_name):
        code = CODES.form_xml if attachment_name == "form.xml" else CODES.form_attachment
        try:
            return get_blob_db().metadb.get(
                parent_id=form_id,
                type_code=code,
                name=attachment_name,
            )
        except BlobMeta.DoesNotExist:
            raise AttachmentNotFound(form_id, attachment_name)

    def get_attachment_content(self, form_id, attachment_name):
        meta = self.get_attachment_by_name(form_id, attachment_name)
        return AttachmentContent(meta.content_type, meta.open(), meta.content_length)

    def get_forms_with_attachments_meta(self, form_ids, ordered=False):
        assert isinstance(form_ids, list)
        if not form_ids:
            return []
        forms = list(self.get_forms(form_ids))

        attachments = sorted(
            get_blob_db().metadb.get_for_parents(form_ids),
            key=lambda meta: meta.parent_id
        )
        forms_by_id = {form.form_id: form for form in forms}
        attach_prefetch_models(forms_by_id, attachments, 'parent_id', 'attachments_list')

        if ordered:
            sort_with_id_list(forms, form_ids, 'form_id')

        return forms

    def modify_attachment_xml_and_metadata(self, form_data, form_attachment_new_xml):
        attachment_metadata = form_data.get_attachment_meta("form.xml")
        # Write the new xml to the database
        if isinstance(form_attachment_new_xml, bytes):
            form_attachment_new_xml = BytesIO(form_attachment_new_xml)
        get_blob_db().put(form_attachment_new_xml, meta=attachment_metadata)
        operation = XFormOperation(user_id=SYSTEM_USER_ID, date=datetime.utcnow(),
                                   operation=XFormOperation.GDPR_SCRUB)
        form_data.track_create(operation)
        self.update_form(form_data)

    def get_forms_by_type(self, domain, type_, limit, recent_first=False):
        state = self.model.DOC_TYPE_TO_STATE[type_]
        assert limit is not None
        # apply limit in python as well since we may get more results than we expect
        # if we're in a sharded environment
        forms = self.plproxy_raw(
            'SELECT * from get_forms_by_state(%s, %s, %s, %s)',
            [domain, state, limit, recent_first]
        )
        forms = sorted(forms, key=lambda f: f.received_on, reverse=recent_first)
        return forms[:limit]

    def get_form_ids_in_domain(self, domain, doc_type="XFormInstance"):
        """Get all form ids of doc type in domain

        Old names: get_all_form_ids_in_domain, get_form_ids_in_domain_by_type
        """
        state = self.model.DOC_TYPE_TO_STATE[doc_type]
        return self.get_form_ids_in_domain_by_state(domain, state)

    def get_form_ids_in_domain_by_state(self, domain, state):
        with self.model.get_plproxy_cursor(readonly=True) as cursor:
            cursor.execute(
                'SELECT form_id from get_form_ids_in_domain_by_type(%s, %s)',
                [domain, state]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.form_id for result in results]

    def get_deleted_form_ids_in_domain(self, domain):
        result = []
        for db_name in get_db_aliases_for_partitioned_query():
            result.extend(
                self.using(db_name)
                .filter(domain=domain, deleted_on__isnull=False)
                .values_list('form_id', flat=True)
            )
        return result

    def iter_form_ids_by_xmlns(self, domain, xmlns=None):
        q_expr = Q(domain=domain) & Q(state=self.model.NORMAL)
        if xmlns:
            q_expr &= Q(xmlns=xmlns)
        for form_id in paginate_query_across_partitioned_databases(
                self.model, q_expr, values=['form_id'], load_source='formids_by_xmlns'):
            yield form_id[0]

    def get_form_ids_for_user(self, domain, user_id):
        return self._get_form_ids_for_user(domain, user_id, is_deleted=False)

    def get_deleted_form_ids_for_user(self, domain, user_id):
        return self._get_form_ids_for_user(domain, user_id, is_deleted=True)

    def _get_form_ids_for_user(self, domain, user_id, is_deleted):
        with self.model.get_plproxy_cursor(readonly=True) as cursor:
            cursor.execute(
                'SELECT form_id FROM get_form_ids_for_user_2(%s, %s, %s)',
                [domain, user_id, is_deleted]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.form_id for result in results]

    def set_archived_state(self, form, archive, user_id):
        from casexml.apps.case.xform import get_case_ids_from_form
        form_id = form.form_id
        case_ids = list(get_case_ids_from_form(form))
        with self.model.get_plproxy_cursor() as cursor:
            cursor.execute('SELECT archive_unarchive_form(%s, %s, %s)', [form_id, user_id, archive])
            cursor.execute('SELECT revoke_restore_case_transactions_for_form(%s, %s, %s)',
                           [case_ids, form_id, archive])
        form.state = self.model.ARCHIVED if archive else self.model.NORMAL

    @staticmethod
    def do_archive(form, archive, user_id, trigger_signals):
        """Un/archive form

        :param form: the form to be archived or unarchived.
        :param archive: Boolean value. Archive if true else unarchive.
        :param user_id: id of user performing the action.
        """
        args = [form, archive, user_id, trigger_signals]
        args_json = [form.form_id, archive, user_id, trigger_signals]
        system_action.submit(ARCHIVE_FORM, args, args_json, form.domain)

    @system_action(ARCHIVE_FORM)
    def _do_archive(form, archive, user_id, trigger_signals):
        """ARCHIVE_FORM system action

        This method is not meant to be called directly. It is called
        when an ARCHIVE_FORM system action is submitted.

        :param form: form to be un/archived.
        :param archive: Boolean value. Archive if true else unarchive.
        :param user_id: id of user performing the action.
        """
        unfinished = XFormInstanceManager._unfinished_archive
        with unfinished(form, archive, user_id, trigger_signals) as archive_stub:
            XFormInstance.objects.set_archived_state(form, archive, user_id)
            archive_stub.archive_history_updated()

    @classmethod
    def publish_archive_action_to_kafka(cls, form, user_id, archive):
        with cls._unfinished_archive(form, archive, user_id):
            pass

    @staticmethod
    @contextmanager
    def _unfinished_archive(form, archive, user_id, trigger_signals=True):
        from ..change_publishers import publish_form_saved
        with unfinished_archive(instance=form, user_id=user_id, archive=archive) as archive_stub:
            yield archive_stub
            publish_form_saved(form)
            if trigger_signals:
                signal = xform_archived if archive else xform_unarchived
                signal.send(sender="form_processor", xform=form)

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

    def update_form_problem_and_state(self, form):
        with self.model.get_plproxy_cursor() as cursor:
            cursor.execute(
                'SELECT update_form_problem_and_state(%s, %s, %s)',
                [form.form_id, form.problem, form.state]
            )

    def update_form(self, form, publish_changes=True):
        from ..change_publishers import publish_form_saved
        assert form.is_saved(), "this method doesn't support creating unsaved forms"
        assert not form.has_unsaved_attachments(), 'Adding attachments to saved form not supported'
        assert not form.has_tracked_models_to_delete(), 'Deleting other models not supported by this method'
        assert not form.has_tracked_models_to_update(), 'Updating other models not supported by this method'
        assert not form.has_tracked_models_to_create(BlobMeta), \
            'Adding new attachments not supported by this method'

        new_operations = form.get_tracked_models_to_create(XFormOperation)
        db_name = form.db
        if form.orig_id:
            old_db_name = get_db_alias_for_partitioned_doc(form.orig_id)
            assert old_db_name == db_name, "this method doesn't support moving the form to new db"

        with transaction.atomic(using=db_name):
            if form.form_id_updated():
                operations = form.original_operations + new_operations
                form.save()
                get_blob_db().metadb.reparent(form.orig_id, form.form_id)
                for model in operations:
                    model.form = form
                    model.save()
            else:
                with transaction.atomic(db_name):
                    form.save()
                    for operation in new_operations:
                        operation.form = form
                        operation.save()

        if publish_changes:
            publish_form_saved(form)

    def soft_delete_forms(self, domain, form_ids, deletion_date=None, deletion_id=None):
        assert isinstance(form_ids, list)
        deletion_date = deletion_date or datetime.utcnow()
        with self.model.get_plproxy_cursor() as cursor:
            cursor.execute(
                'SELECT soft_delete_forms_3(%s, %s, %s, %s) as affected_count',
                [domain, form_ids, deletion_date, deletion_id]
            )
            results = fetchall_as_namedtuple(cursor)
            affected_count = sum([result.affected_count for result in results])

        self.publish_deleted_forms(domain, form_ids)

        return affected_count

    def soft_undelete_forms(self, domain, form_ids):
        from ..change_publishers import publish_form_saved
        assert isinstance(form_ids, list)
        problem = 'Restored on {}'.format(datetime.utcnow())
        with self.model.get_plproxy_cursor() as cursor:
            cursor.execute(
                'SELECT soft_undelete_forms_3(%s, %s, %s) as affected_count',
                [domain, form_ids, problem]
            )
            results = fetchall_as_namedtuple(cursor)
            count = sum([result.affected_count for result in results])

        for form_ids_chunk in chunked(form_ids, 500):
            forms = self.get_forms(list(form_ids_chunk))
            for form in forms:
                publish_form_saved(form)

        return count

    def hard_delete_forms(self, domain, form_ids, delete_attachments=True, *,
                          publish_changes=True, leave_tombstone=False):
        """Delete forms permanently. Currently only used for tests, domain deletion and to delete system forms
        and so do not need to leave tombstones.

        :param publish_changes: Flag for change feed publication.
            Documents in Elasticsearch will not be deleted if this is false.
        :param leave_tombstone: Currently unimplemented. Should be set to True if you are using it for any other
            reason than stated above.
        """
        assert isinstance(form_ids, list)

        if leave_tombstone:
            raise NotImplementedError(
                """
                hard_delete_forms is currently only used for tests, domain deletion and to delete system forms.
                If you are trying to hard delete forms for any other reason you'll need to implement a way to
                create tombstones for the forms you're trying to delete.
                """
            )

        deleted_count = 0
        for db_name, split_form_ids in split_list_by_db_partition(form_ids):
            # cascade should delete the operations
            _, deleted_models = self.using(db_name).filter(
                domain=domain, form_id__in=split_form_ids
            ).delete()
            deleted_count += deleted_models.get(self.model._meta.label, 0)

        if delete_attachments and deleted_count:
            if deleted_count != len(form_ids):
                # in the unlikely event that we didn't delete all forms (because they weren't all
                # in the specified domain), only delete attachments for forms that were deleted.
                deleted_forms = [
                    form_id for form_id in form_ids
                    if not self.form_exists(form_id)
                ]
            else:
                deleted_forms = form_ids
            metas = get_blob_db().metadb.get_for_parents(deleted_forms)
            get_blob_db().bulk_delete(metas=metas)

        if publish_changes:
            self.publish_deleted_forms(domain, form_ids)

        return deleted_count

    def hard_delete_forms_before_cutoff(self, cutoff, dry_run=True):
        """
        Permanently deletes forms with deleted_on set to a datetime earlier than
        the specified cutoff datetime and creates a tombstone record of the deletion.
        :param cutoff: datetime used to obtain the forms to be hard deleted
        :param dry_run: if True, no changes will be committed to the database
        and this method is effectively read-only
        :return: dictionary of count of deleted objects per table
        """
        counts = {}
        class_path = 'form_processor.XFormInstance'
        for db_name in get_db_aliases_for_partitioned_query():
            queryset = self.using(db_name).filter(deleted_on__lt=cutoff)
            if dry_run:
                deleted_counts = {class_path: queryset.count()}
                counts.update(deleted_counts)
            else:
                form_tombstones = [DeletedSQLDoc(doc_id=form.form_id, object_class_path=class_path,
                                                 domain=form.domain, deleted_on=form.deleted_on)
                                   for form in queryset]
                for chunk in chunked(form_tombstones, 1000, list):
                    DeletedSQLDoc.objects.bulk_create(chunk, ignore_conflicts=True)
                deleted_counts = queryset.delete()[1]
                counts.update(deleted_counts)
        return counts

    @staticmethod
    def publish_deleted_forms(domain, form_ids):
        from ..change_publishers import publish_form_deleted
        for form_id in form_ids:
            publish_form_deleted(domain, form_id)


class XFormOperationManager(RequireDBManager):

    def get_form_operations(self, form_id):
        return list(self.partitioned_query(form_id).filter(form_id=form_id).order_by('date'))


class XFormInstance(PartitionedModel, models.Model, RedisLockableMixIn,
                    AttachmentMixin, TrackRelatedChanges):
    partition_attr = 'form_id'

    # states should be powers of 2
    NORMAL = 1
    ARCHIVED = 2
    DEPRECATED = 4
    DUPLICATE = 8
    ERROR = 16
    SUBMISSION_ERROR_LOG = 32
    STATES = (
        (NORMAL, 'normal'),
        (ARCHIVED, 'archived'),
        (DEPRECATED, 'deprecated'),
        (DUPLICATE, 'duplicate'),
        (ERROR, 'error'),
        (SUBMISSION_ERROR_LOG, 'submission_error'),
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
        return XFormOperation.objects.get_form_operations(self.__original_form_id)

    def natural_key(self):
        """
        Django requires returning a tuple in natural_key methods:
        https://docs.djangoproject.com/en/3.2/topics/serialization/#serialization-of-natural-keys
        We intentionally do not follow this to optimize corehq.apps.dump_reload.sql.load.SqlDataLoader when other
        models reference CommCareCase or XFormInstance via a foreign key. This means our loader code may break in
        future Django upgrades.
        """
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
        return bool(self.deleted_on)

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
        operations = XFormOperation.objects.get_form_operations(self.form_id) if self.is_saved() else []
        operations += self.get_tracked_models_to_create(XFormOperation)
        return operations

    @property
    def metadata(self):
        from ..utils import clean_metadata
        if const.TAG_META in self.form_data:
            return XFormPhoneMetadata.wrap(clean_metadata(self.form_data[const.TAG_META]))

    @property
    def type(self):
        return self.form_data.get(const.TAG_TYPE, "")

    @property
    def name(self):
        return self.form_data.get(const.TAG_NAME, "")

    @memoized
    def get_sync_token(self):
        from casexml.apps.phone.exceptions import MissingSyncLog
        from casexml.apps.phone.models import get_properly_wrapped_sync_log
        if self.last_sync_token:
            try:
                return get_properly_wrapped_sync_log(self.last_sync_token)
            except MissingSyncLog:
                pass
        return None

    def soft_delete(self):
        deleted_on = datetime.utcnow()
        type(self).objects.soft_delete_forms(self.domain, [self.form_id], deleted_on)
        self.deleted_on = deleted_on

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
        return type(self).objects.get_attachment_by_name(self.form_id, attachment_name)

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
        if not self.is_archived:
            type(self).objects.do_archive(self, True, user_id, trigger_signals)

    def unarchive(self, user_id=None, trigger_signals=True):
        if self.is_archived:
            type(self).objects.do_archive(self, False, user_id, trigger_signals)

    def delete(self, leave_tombstone=True):
        if not settings.UNIT_TESTING:
            if not leave_tombstone:
                raise ValueError(
                    'Cannot delete form without leaving a tombstone except during testing, domain deletion or '
                    'when deleting system forms')
            create_deleted_sql_doc(self.form_id, 'form_processor.XFormInstance', self.domain, self.deleted_on)

        super().delete()

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
            models.Index(fields=['xmlns']),
            models.Index(fields=['deleted_on'],
                         name=create_unique_index_name('form_processor',
                                                       'xforminstance',
                                                       ['deleted_on']),
                         condition=models.Q(deleted_on__isnull=False))
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

    objects = XFormOperationManager()

    form = models.ForeignKey(XFormInstance, to_field='form_id', on_delete=models.CASCADE)
    user_id = models.CharField(max_length=255, null=True)
    operation = models.CharField(max_length=255, default=None)
    date = models.DateTimeField(null=False)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.form_id, self.user_id, self.date

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
        from looseversion import LooseVersion
        version_text = get_commcare_version_from_appversion_text(self.appVersion)
        if version_text:
            return LooseVersion(version_text)
