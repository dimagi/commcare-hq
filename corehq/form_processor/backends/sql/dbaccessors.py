from __future__ import absolute_import

from __future__ import unicode_literals
import functools
import itertools
import logging
import struct
from abc import ABCMeta, abstractproperty
from abc import abstractmethod
from collections import namedtuple
from datetime import datetime
from io import BytesIO
from itertools import groupby
from uuid import UUID

import csiphash
import re

import operator
import six
from ddtrace import tracer
from django.conf import settings
from django.db import connections, InternalError, transaction
from django.db.models import Q, F
from django.db.models.functions import Greatest, Concat
from django.db.models.expressions import Value

from casexml.apps.case.xform import get_case_updates
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.blobs import get_blob_db, CODES
from corehq.blobs.models import BlobMeta
from corehq.form_processor.exceptions import (
    XFormNotFound,
    XFormSaveError,
    CaseNotFound,
    AttachmentNotFound,
    CaseSaveError,
    LedgerSaveError,
    LedgerValueNotFound)
from corehq.form_processor.interfaces.dbaccessors import (
    AbstractCaseAccessor,
    AbstractFormAccessor,
    CaseIndexInfo,
    AttachmentContent,
    AbstractLedgerAccessor
)
from corehq.form_processor.models import (
    XFormInstanceSQL,
    CommCareCaseIndexSQL,
    CaseAttachmentSQL,
    CaseTransaction,
    CommCareCaseSQL,
    XFormOperationSQL,
    LedgerValue,
    LedgerTransaction,
)
from corehq.form_processor.utils.sql import (
    fetchone_as_namedtuple,
    fetchall_as_namedtuple
)
from corehq.sql_db.config import partition_config
from corehq.sql_db.routers import db_for_read_write, get_cursor
from corehq.sql_db.util import (
    split_list_by_db_partition,
    get_db_aliases_for_partitioned_query,
)
from corehq.util.datadog.utils import form_load_counter
from corehq.util.queries import fast_distinct_in_domain
from corehq.util.soft_assert import soft_assert
from dimagi.utils.chunked import chunked

doc_type_to_state = {
    "XFormInstance": XFormInstanceSQL.NORMAL,
    "XFormError": XFormInstanceSQL.ERROR,
    "XFormDuplicate": XFormInstanceSQL.DUPLICATE,
    "XFormDeprecated": XFormInstanceSQL.DEPRECATED,
    "XFormArchived": XFormInstanceSQL.ARCHIVED,
    "SubmissionErrorLog": XFormInstanceSQL.SUBMISSION_ERROR_LOG
}


def iter_all_rows(reindex_accessor):
    """Returns a generator that will iterate over all rows provided by the
    reindex accessor
    """
    for db_alias in reindex_accessor.sql_db_aliases:
        docs = reindex_accessor.get_docs(db_alias)
        while docs:
            for doc in docs:
                yield doc

            last_id = getattr(doc, reindex_accessor.primary_key_field_name)
            docs = reindex_accessor.get_docs(db_alias, last_doc_pk=last_id)


def iter_all_ids(reindex_accessor):
    return itertools.chain.from_iterable(iter_all_ids_chunked(reindex_accessor))


def iter_all_ids_chunked(reindex_accessor):
    for db_alias in reindex_accessor.sql_db_aliases:
        docs = list(reindex_accessor.get_doc_ids(db_alias))
        while docs:
            yield [d.doc_id for d in docs]

            last_id = docs[-1].primary_key
            docs = list(reindex_accessor.get_doc_ids(db_alias, last_doc_pk=last_id))


class ShardAccessor(object):
    hash_key = b'\x00' * 16

    @staticmethod
    def hash_doc_ids_sql_for_testing(doc_ids):
        """Get HASH for each doc_id from PostgreSQL

        This is used to ensure the python version is consistent with what's
        being used by PL/Proxy
        """
        assert settings.USE_PARTITIONED_DATABASE

        params = ','.join(["(%s)"] * len(doc_ids))
        query = """
            SELECT doc_id, hash_string(doc_id, 'siphash24') AS hash
            FROM (VALUES {}) AS t (doc_id)
        """.format(params)
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(query, doc_ids)
            rows = fetchall_as_namedtuple(cursor)
            return {row.doc_id: row.hash for row in rows}

    @staticmethod
    def hash_doc_uuid_sql_for_testing(doc_uuid):
        """Get the hash for a UUID from PostgreSQL

        This is used to ensure the python version is consistent with what's
        being used by PL/Proxy
        """
        assert settings.USE_PARTITIONED_DATABASE

        if not isinstance(doc_uuid, UUID):
            raise ValueError("Expected an instance of UUID")

        query = "SELECT hash_string(CAST(%s AS bytea), 'siphash24') AS hash"
        with get_cursor(XFormInstanceSQL) as cursor:
            doc_uuid_before_cast = '\\x%s' % doc_uuid.hex
            cursor.execute(query, [doc_uuid_before_cast])
            return fetchone_as_namedtuple(cursor).hash

    @staticmethod
    def hash_doc_ids_python(doc_ids):
        return {
            doc_id: ShardAccessor.hash_doc_id_python(doc_id)
            for doc_id in doc_ids
        }

    @staticmethod
    def hash_doc_id_python(doc_id):
        if isinstance(doc_id, six.text_type):
            doc_id = doc_id.encode('utf-8')
        elif isinstance(doc_id, UUID):
            # Hash the 16-byte string
            doc_id = doc_id.bytes

        digest = csiphash.siphash24(ShardAccessor.hash_key, doc_id)
        hash_long = struct.unpack("<Q", digest)[0]  # convert byte string to long
        # convert 64 bit hash to 32 bit to match Postgres
        return hash_long & 0xffffffff

    @staticmethod
    def get_database_for_docs(doc_ids):
        """
        :param doc_ids:
        :return: Dict of ``doc_id -> Django DB alias``
        """
        assert settings.USE_PARTITIONED_DATABASE, """Partitioned DB not in use,
        consider using `corehq.sql_db.get_db_alias_for_partitioned_doc` instead"""
        databases = {}
        shard_map = partition_config.get_django_shard_map()
        part_mask = len(shard_map) - 1
        for chunk in chunked(doc_ids, 100):
            hashes = ShardAccessor.hash_doc_ids_python(chunk)
            shards = {doc_id: hash_ & part_mask for doc_id, hash_ in hashes.items()}
            databases.update({
                doc_id: shard_map[shard_id].django_dbname for doc_id, shard_id in shards.items()
            })

        return databases

    @staticmethod
    def get_shard_id_and_database_for_doc(doc_id):
        assert settings.USE_PARTITIONED_DATABASE, """Partitioned DB not in use,
        consider using `corehq.sql_db.get_db_alias_for_partitioned_doc` instead"""
        shard_map = partition_config.get_django_shard_map()
        part_mask = len(shard_map) - 1
        hash_ = ShardAccessor.hash_doc_id_python(doc_id)
        shard_id = hash_ & part_mask
        return shard_id, shard_map[shard_id].django_dbname

    @staticmethod
    def get_database_for_doc(doc_id):
        """
        :return: Django DB alias in which the doc should be stored
        """
        return ShardAccessor.get_shard_id_and_database_for_doc(doc_id)[1]


DocIds = namedtuple('DocIds', 'doc_id primary_key')


class ReindexAccessor(six.with_metaclass(ABCMeta)):
    primary_key_field_name = 'id'

    def __init__(self, limit_db_aliases=None):
        self.limit_db_aliases = limit_db_aliases

    def is_sharded(self):
        """
        :return: True the django model is sharded, otherwise false.
        """
        from corehq.sql_db.models import PartitionedModel
        return issubclass(self.model_class, PartitionedModel)

    @property
    def sql_db_aliases(self):
        all_db_aliases = get_db_aliases_for_partitioned_query() if self.is_sharded() \
            else [db_for_read_write(self.model_class)]
        if self.limit_db_aliases:
            db_aliases = list(set(all_db_aliases) & set(self.limit_db_aliases))
            assert db_aliases, 'Limited DBs not in expected list: {} {}'.format(
                all_db_aliases, self.limit_db_aliases
            )
            return db_aliases
        return all_db_aliases

    @abstractproperty
    def model_class(self):
        """
        :return: the django model class belonging to this reindexer
        """
        raise NotImplementedError

    @abstractproperty
    def id_field(self):
        """
        :return: The name of the model field to return when calling ``get_doc_ids``. Return a string
                 or a dict mapping an alias to a SQL expression
        """
        raise NotImplementedError

    @abstractmethod
    def get_doc(self, doc_id):
        """
        :param doc_id: ID of the doc
        :return: The doc with the given ID
        """
        raise NotImplementedError

    def doc_to_json(self, doc):
        """
        :param doc:
        :return: The JSON representation of the doc
        """
        return doc.to_json()

    def filters(self, last_doc_pk=None, for_count=False):
        filters = []
        if last_doc_pk is not None:
            filters.append(Q(**{self.primary_key_field_name + "__gt": last_doc_pk}))
        filters.extend(self.extra_filters(for_count=for_count))
        return functools.reduce(operator.and_, filters) if filters else None

    def query(self, from_db, last_doc_pk=None, for_count=False):
        filters = self.filters(last_doc_pk, for_count)
        query = self.model_class.objects.using(from_db)
        if filters:
            query = query.filter(filters)
        return query

    def get_doc_ids(self, from_db, last_doc_pk=None, limit=500):
        """
        :param from_db: The DB alias to query
        :param last_doc_pk: The primary key of the last doc from the previous batch
        :param limit: Desired batch size
        :return: Generator of DocIds namedtuple
        """
        query = self.query(from_db, last_doc_pk)
        field = self.id_field
        if isinstance(field, dict):
            query = query.annotate(**field)
            field = list(field)[0]
        query = query.values(self.primary_key_field_name, field)
        for row in query.order_by(self.primary_key_field_name)[:limit]:
            yield DocIds(row[field], row[self.primary_key_field_name])

    def get_docs(self, from_db, last_doc_pk=None, limit=500):
        """Get a batch of
        :param from_db: The DB alias to query
        :param last_doc_pk: The primary key of the last doc from the previous batch
        :param limit: Desired batch size
        :return: List of documents
        """
        query = self.query(from_db, last_doc_pk)
        return query.order_by(self.primary_key_field_name)[:limit]

    def extra_filters(self, for_count=False):
        """
        :param for_count: True if only filters required for the count query. Only simple filters
                          should be included for the count query.
        :return: list of sql filters
        """
        return []

    def get_approximate_doc_count(self, from_db):
        """Get the approximate doc count from the given DB
        :param from_db: The DB alias to query
        """
        query = self.query(from_db, for_count=True)
        sql, params = query.query.sql_with_params()
        explain_query = 'EXPLAIN {}'.format(sql)
        db_cursor = connections[from_db].cursor()
        with db_cursor as cursor:
            cursor.execute(explain_query, params)
            for row in cursor.fetchall():
                search = re.search(r' rows=(\d+)', row[0])
                if search:
                    return int(search.group(1))
        return 0


class FormReindexAccessor(ReindexAccessor):

    def __init__(self, domain=None, include_attachments=True, limit_db_aliases=None, include_deleted=False):
        super(FormReindexAccessor, self).__init__(limit_db_aliases)
        self.domain = domain
        self.include_attachments = include_attachments
        self.include_deleted = include_deleted

    @property
    def model_class(self):
        return XFormInstanceSQL

    @property
    def id_field(self):
        return 'form_id'

    def get_doc(self, doc_id):
        try:
            return FormAccessorSQL.get_form(doc_id)
        except XFormNotFound:
            pass

    def doc_to_json(self, doc):
        return doc.to_json(include_attachments=self.include_attachments)

    def extra_filters(self, for_count=False):
        filters = []
        if not (for_count or self.include_deleted):
            # don't inlucde in count query since the query planner can't account for it
            # hack for django: 'state & DELETED = 0' so 'state = state + state & DELETED'
            filters.append(Q(state=F('state').bitand(XFormInstanceSQL.DELETED) + F('state')))
        if self.domain:
            filters.append(Q(domain=self.domain))
        return filters


class FormAccessorSQL(AbstractFormAccessor):

    @staticmethod
    def get_form(form_id):
        try:
            return XFormInstanceSQL.objects.partitioned_get(form_id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound(form_id)

    @staticmethod
    def get_forms(form_ids, ordered=False):
        assert isinstance(form_ids, list)
        if not form_ids:
            return []
        forms = list(XFormInstanceSQL.objects.raw('SELECT * from get_forms_by_id(%s)', [form_ids]))
        if ordered:
            _sort_with_id_list(forms, form_ids, 'form_id')

        return forms

    @staticmethod
    def get_attachments(form_id):
        return get_blob_db().metadb.get_for_parent(form_id)

    @staticmethod
    def iter_forms_by_last_modified(start_datetime, end_datetime):
        '''
        Returns all forms that have been modified within a time range. The start date is
        exclusive while the end date is inclusive (start_datetime, end_datetime].

        NOTE: This does not include archived forms

        :param start_datetime: The start date of which modified forms must be greater than
        :param end_datetime: The end date of which modified forms must be less than or equal to

        :returns: An iterator of XFormInstanceSQL objects
        '''
        from corehq.sql_db.util import paginate_query_across_partitioned_databases

        annotate = {
            'last_modified': Greatest('received_on', 'edited_on', 'deleted_on'),
        }

        return paginate_query_across_partitioned_databases(
            XFormInstanceSQL,
            Q(last_modified__gt=start_datetime, last_modified__lte=end_datetime),
            annotate=annotate,
        )

    @staticmethod
    def iter_form_ids_by_xmlns(domain, xmlns=None):
        from corehq.sql_db.util import paginate_query_across_partitioned_databases

        q_expr = Q(domain=domain) & Q(state=XFormInstanceSQL.NORMAL)
        if xmlns:
            q_expr &= Q(xmlns=xmlns)

        for form_id in paginate_query_across_partitioned_databases(
                XFormInstanceSQL, q_expr, values=['form_id']):
            yield form_id[0]

    @staticmethod
    def get_with_attachments(form_id):
        """
        It's necessary to store these on the form rather than use a memoized property
        since the form_id can change (in the case of a deprecated form) which breaks
        the memoize hash.
        """
        form = FormAccessorSQL.get_form(form_id)
        form.attachments_list = FormAccessorSQL.get_attachments(form_id)
        return form

    @staticmethod
    def get_attachment_by_name(form_id, attachment_name):
        code = (CODES.form_xml if attachment_name == "form.xml"
                else CODES.form_attachment)
        try:
            return get_blob_db().metadb.get(
                parent_id=form_id,
                type_code=code,
                name=attachment_name,
            )
        except BlobMeta.DoesNotExist:
            raise AttachmentNotFound(attachment_name)

    @staticmethod
    def get_attachment_content(form_id, attachment_name, stream=False):
        meta = FormAccessorSQL.get_attachment_by_name(form_id, attachment_name)
        return AttachmentContent(meta.content_type, meta.open())

    @staticmethod
    def get_form_operations(form_id):
        return list(XFormOperationSQL.objects.raw('SELECT * from get_form_operations(%s)', [form_id]))

    @staticmethod
    def get_forms_with_attachments_meta(form_ids, ordered=False):
        assert isinstance(form_ids, list)
        if not form_ids:
            return []
        forms = list(FormAccessorSQL.get_forms(form_ids))

        attachments = sorted(
            get_blob_db().metadb.get_for_parents(form_ids),
            key=lambda meta: meta.parent_id
        )
        forms_by_id = {form.form_id: form for form in forms}
        _attach_prefetch_models(forms_by_id, attachments, 'parent_id', 'attachments_list')

        if ordered:
            _sort_with_id_list(forms, form_ids, 'form_id')

        return forms

    @staticmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        state = doc_type_to_state[type_]
        assert limit is not None
        # apply limit in python as well since we may get more results than we expect
        # if we're in a sharded environment
        forms = XFormInstanceSQL.objects.raw(
            'SELECT * from get_forms_by_state(%s, %s, %s, %s)',
            [domain, state, limit, recent_first]
        )
        forms = sorted(forms, key=lambda f: f.received_on, reverse=recent_first)
        return forms[:limit]

    @staticmethod
    def form_exists(form_id, domain=None):
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute('SELECT * FROM check_form_exists(%s, %s)', [form_id, domain])
            result = fetchone_as_namedtuple(cursor)
            return result.form_exists

    @staticmethod
    def hard_delete_forms(domain, form_ids, delete_attachments=True):
        assert isinstance(form_ids, list)

        deleted_count = 0
        for db_name, split_form_ids in split_list_by_db_partition(form_ids):
            # cascade should delete the operations
            _, deleted_models = XFormInstanceSQL.objects.using(db_name).filter(
                domain=domain, form_id__in=split_form_ids
            ).delete()
            deleted_count += deleted_models.get(XFormInstanceSQL._meta.label, 0)

        if delete_attachments and deleted_count:
            if deleted_count != len(form_ids):
                # in the unlikely event that we didn't delete all forms (because they weren't all
                # in the specified domain), only delete attachments for forms that were deleted.
                deleted_forms = [
                    form_id for form_id in form_ids
                    if not FormAccessorSQL.form_exists(form_id)
                ]
            else:
                deleted_forms = form_ids
            metas = get_blob_db().metadb.get_for_parents(deleted_forms)
            get_blob_db().bulk_delete(metas=metas)

        return deleted_count

    @staticmethod
    def archive_form(form, user_id):
        from corehq.form_processor.change_publishers import publish_form_saved
        FormAccessorSQL._archive_unarchive_form(form, user_id, archive=True)
        form.state = XFormInstanceSQL.ARCHIVED
        publish_form_saved(form)

    @staticmethod
    def unarchive_form(form, user_id):
        from corehq.form_processor.change_publishers import publish_form_saved
        FormAccessorSQL._archive_unarchive_form(form, user_id, archive=False)
        form.state = XFormInstanceSQL.NORMAL
        publish_form_saved(form)

    @staticmethod
    def soft_undelete_forms(domain, form_ids):
        from corehq.form_processor.change_publishers import publish_form_saved

        assert isinstance(form_ids, list)
        problem = 'Restored on {}'.format(datetime.utcnow())
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT soft_undelete_forms(%s, %s, %s) as affected_count',
                [domain, form_ids, problem]
            )
            results = fetchall_as_namedtuple(cursor)
            return_value = sum([result.affected_count for result in results])

        for form_ids_chunk in chunked(form_ids, 500):
            forms = FormAccessorSQL.get_forms(list(form_ids_chunk))
            for form in forms:
                publish_form_saved(form)

        return return_value

    @staticmethod
    def modify_attachment_xml_and_metadata(form_data, form_attachment_new_xml, _):
        attachment_metadata = form_data.get_attachment_meta("form.xml")
        # Write the new xml to the database
        if isinstance(form_attachment_new_xml, bytes):
            form_attachment_new_xml = BytesIO(form_attachment_new_xml)
        get_blob_db().put(form_attachment_new_xml, meta=attachment_metadata)
        operation = XFormOperationSQL(user_id=SYSTEM_USER_ID, date=datetime.utcnow(),
                                      operation=XFormOperationSQL.GDPR_SCRUB)
        form_data.track_create(operation)
        FormAccessorSQL.update_form(form_data)

    @staticmethod
    def soft_delete_forms(domain, form_ids, deletion_date=None, deletion_id=None):
        from corehq.form_processor.change_publishers import publish_form_deleted
        assert isinstance(form_ids, list)
        deletion_date = deletion_date or datetime.utcnow()
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT soft_delete_forms(%s, %s, %s, %s) as affected_count',
                [domain, form_ids, deletion_date, deletion_id]
            )
            results = fetchall_as_namedtuple(cursor)
            affected_count = sum([result.affected_count for result in results])

        for form_id in form_ids:
            publish_form_deleted(domain, form_id)

        return affected_count

    @staticmethod
    @transaction.atomic
    def _archive_unarchive_form(form, user_id, archive):
        from casexml.apps.case.xform import get_case_ids_from_form
        form_id = form.form_id
        case_ids = list(get_case_ids_from_form(form))
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute('SELECT archive_unarchive_form(%s, %s, %s)', [form_id, user_id, archive])
            cursor.execute('SELECT revoke_restore_case_transactions_for_form(%s, %s, %s)',
                           [case_ids, form_id, archive])

    @staticmethod
    @transaction.atomic
    def save_new_form(form):
        """
        Save a previously unsaved form
        """
        assert not form.is_saved(), 'form already saved'
        logging.debug('Saving new form: %s', form)

        operations = form.get_tracked_models_to_create(XFormOperationSQL)
        for operation in operations:
            if operation.is_saved():
                raise XFormSaveError(
                    'XFormOperationSQL {} has already been saved'.format(operation.id)
                )
            operation.form_id = form.form_id

        try:
            with form.attachment_writer() as write_attachments, \
                    transaction.atomic(using=form.db, savepoint=False):
                form.save()
                write_attachments()
                for operation in operations:
                    operation.save()
        except InternalError as e:
            raise XFormSaveError(e)

        form.clear_tracked_models()

    @staticmethod
    def update_form(form, publish_changes=True):
        from corehq.form_processor.change_publishers import publish_form_saved
        from corehq.sql_db.util import get_db_alias_for_partitioned_doc
        assert form.is_saved(), "this method doesn't support creating unsaved forms"
        assert not form.has_unsaved_attachments(), \
            'Adding attachments to saved form not supported'
        assert not form.has_tracked_models_to_delete(), 'Deleting other models not supported by this method'
        assert not form.has_tracked_models_to_update(), 'Updating other models not supported by this method'
        assert not form.has_tracked_models_to_create(BlobMeta), \
            'Adding new attachments not supported by this method'

        new_operations = form.get_tracked_models_to_create(XFormOperationSQL)
        db_name = form.db
        if form.orig_id:
            old_db_name = get_db_alias_for_partitioned_doc(form.orig_id)
            assert old_db_name == db_name, "this method doesn't support moving the form to new db"

        with transaction.atomic(using=db_name):
            if form.form_id_updated():
                operations = form.original_operations + new_operations
                with transaction.atomic(db_name):
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

    @staticmethod
    @transaction.atomic
    def update_form_problem_and_state(form):
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT update_form_problem_and_state(%s, %s, %s)',
                [form.form_id, form.problem, form.state]
            )

    @staticmethod
    def get_deleted_form_ids_for_user(domain, user_id):
        return FormAccessorSQL._get_form_ids_for_user(
            domain,
            user_id,
            True,
        )

    @staticmethod
    def get_form_ids_in_domain_by_type(domain, type_):
        state = doc_type_to_state[type_]
        return FormAccessorSQL.get_form_ids_in_domain_by_state(domain, state)

    @staticmethod
    def get_deleted_form_ids_in_domain(domain):
        deleted_state = XFormInstanceSQL.NORMAL | XFormInstanceSQL.DELETED
        return FormAccessorSQL.get_form_ids_in_domain_by_state(domain, deleted_state)

    @staticmethod
    def get_form_ids_in_domain_by_state(domain, state):
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT form_id from get_form_ids_in_domain_by_type(%s, %s)',
                [domain, state]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.form_id for result in results]

    @staticmethod
    def get_form_ids_for_user(domain, user_id):
        return FormAccessorSQL._get_form_ids_for_user(
            domain,
            user_id,
            False,
        )

    @staticmethod
    def _get_form_ids_for_user(domain, user_id, is_deleted):
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT form_id FROM get_form_ids_for_user(%s, %s, %s)',
                [domain, user_id, is_deleted]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.form_id for result in results]


class CaseReindexAccessor(ReindexAccessor):
    """
    :param: domain: If supplied the accessor will restrict results to only that domain
    """
    def __init__(self, domain=None, limit_db_aliases=None, start_date=None, end_date=None, case_type=None,
                 include_deleted=False):
        super(CaseReindexAccessor, self).__init__(limit_db_aliases=limit_db_aliases)
        self.domain = domain
        self.start_date = start_date
        self.end_date = end_date
        self.case_type = case_type
        self.include_deleted = include_deleted

    @property
    def model_class(self):
        return CommCareCaseSQL

    @property
    def id_field(self):
        return 'case_id'

    def get_doc(self, doc_id):
        try:
            return CaseAccessorSQL.get_case(doc_id)
        except CaseNotFound:
            pass

    def extra_filters(self, for_count=False):
        filters = [] if self.include_deleted else [Q(deleted=False)]
        if self.domain:
            filters.append(Q(domain=self.domain))
        if self.start_date is not None:
            filters.append(Q(server_modified_on__gte=self.start_date))
        if self.end_date is not None:
            filters.append(Q(server_modified_on__lt=self.end_date))
        if self.case_type is not None:
            filters.append(Q(type=self.case_type))
        return filters


class CaseAccessorSQL(AbstractCaseAccessor):

    @staticmethod
    def get_case(case_id):
        try:
            return CommCareCaseSQL.objects.partitioned_get(case_id)
        except CommCareCaseSQL.DoesNotExist:
            raise CaseNotFound

    @staticmethod
    def get_cases(case_ids, ordered=False, prefetched_indices=None):
        assert isinstance(case_ids, list)
        if not case_ids:
            return []
        cases = list(CommCareCaseSQL.objects.raw('SELECT * from get_cases_by_id(%s)', [case_ids]))

        if ordered:
            _sort_with_id_list(cases, case_ids, 'case_id')

        if prefetched_indices:
            cases_by_id = {case.case_id: case for case in cases}
            _attach_prefetch_models(
                cases_by_id, prefetched_indices, 'case_id', 'cached_indices')

        return cases

    @staticmethod
    def case_exists(case_id):
        return CommCareCaseSQL.objects.partitioned_query(case_id).filter(case_id=case_id).exists()

    @staticmethod
    def get_case_xform_ids(case_id):
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT form_id FROM get_case_transactions_by_type(%s, %s)',
                [case_id, CaseTransaction.TYPE_FORM]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.form_id for result in results]

    @staticmethod
    def get_indices(domain, case_id):
        return list(CommCareCaseIndexSQL.objects.raw(
            'SELECT * FROM get_case_indices(%s, %s)', [domain, case_id]
        ))

    @staticmethod
    def get_reverse_indices(domain, case_id):
        indices = list(CommCareCaseIndexSQL.objects.raw(
            'SELECT * FROM get_case_indices_reverse(%s, %s)', [domain, case_id]
        ))

        def _set_referenced_id(index):
            # see corehq/couchapps/case_indices/views/related/map.js
            index.referenced_id = index.case_id
            return index

        return [_set_referenced_id(index) for index in indices]

    @staticmethod
    def get_all_reverse_indices_info(domain, case_ids):
        assert isinstance(case_ids, list)
        if not case_ids:
            return []

        indexes = CommCareCaseIndexSQL.objects.raw(
            'SELECT * FROM get_all_reverse_indices(%s, %s)',
            [domain, case_ids]
        )
        return [
            CaseIndexInfo(
                case_id=index.case_id,
                identifier=index.identifier,
                referenced_id=index.referenced_id,
                referenced_type=index.referenced_type,
                relationship=index.relationship_id
            ) for index in indexes
        ]

    @staticmethod
    def get_indexed_case_ids(domain, case_ids):
        """
        Given a base list of case ids, gets all ids of cases they reference (parent and host cases)
        """
        if not case_ids:
            return []

        with get_cursor(CommCareCaseIndexSQL) as cursor:
            cursor.execute(
                'SELECT referenced_id FROM get_multiple_cases_indices(%s, %s)',
                [domain, list(case_ids)]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.referenced_id for result in results]

    @staticmethod
    def get_reverse_indexed_cases(domain, case_ids, case_types=None, is_closed=None):
        assert isinstance(case_ids, list)
        assert case_types is None or isinstance(case_types, list)
        if not case_ids:
            return []

        cases = list(CommCareCaseSQL.objects.raw(
            'SELECT * FROM get_reverse_indexed_cases_3(%s, %s, %s, %s)',
            [domain, case_ids, case_types, is_closed])
        )
        cases_by_id = {case.case_id: case for case in cases}
        indices = list(CommCareCaseIndexSQL.objects.raw(
            'SELECT * FROM get_multiple_cases_indices(%s, %s)',
            [domain, list(cases_by_id)])
        )
        _attach_prefetch_models(cases_by_id, indices, 'case_id', 'cached_indices')
        return cases

    @staticmethod
    @tracer.wrap("form_processor.sql.check_transaction_order_for_case")
    def check_transaction_order_for_case(case_id):
        """ Returns whether the order of transactions needs to be reconciled by client_date

        True if the order is fine, False if the order is bad
        """
        if not case_id:
            return False

        from corehq.sql_db.util import get_db_alias_for_partitioned_doc
        db = get_db_alias_for_partitioned_doc(case_id)
        with connections[db].cursor() as cursor:
            cursor.execute(
                'SELECT compare_server_client_case_transaction_order(%s, %s)',
                [case_id, CaseTransaction.case_rebuild_types() | CaseTransaction.TYPE_CASE_CREATE])
            result = cursor.fetchone()[0]
            return result

    @staticmethod
    def hard_delete_cases(domain, case_ids):
        assert isinstance(case_ids, list)
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute('SELECT hard_delete_cases(%s, %s) as deleted_count', [domain, case_ids])
            results = fetchall_as_namedtuple(cursor)
            return sum([result.deleted_count for result in results])

    @staticmethod
    def get_attachment_by_name(case_id, attachment_name):
        try:
            return CaseAttachmentSQL.objects.raw(
                'select * from get_case_attachment_by_name(%s, %s)',
                [case_id, attachment_name]
            )[0]
        except IndexError:
            raise AttachmentNotFound(attachment_name)

    @staticmethod
    def get_attachment_content(case_id, attachment_name):
        meta = CaseAccessorSQL.get_attachment_by_name(case_id, attachment_name)
        return AttachmentContent(meta.content_type, meta.open())

    @staticmethod
    def get_attachments(case_id):
        return list(CaseAttachmentSQL.objects.raw('SELECT * from get_case_attachments(%s)', [case_id]))

    @staticmethod
    def get_transactions(case_id):
        return list(CaseTransaction.objects.raw('SELECT * from get_case_transactions(%s)', [case_id]))

    @staticmethod
    def get_transaction_by_form_id(case_id, form_id):
        transactions = list(CaseTransaction.objects.raw(
            'SELECT * from get_case_transaction_by_form_id(%s, %s)',
            [case_id, form_id])
        )
        assert len(transactions) <= 1
        return transactions[0] if transactions else None

    @staticmethod
    def get_transactions_by_type(case_id, transaction_type):
        return list(CaseTransaction.objects.raw(
            'SELECT * from get_case_transactions_by_type(%s, %s)',
            [case_id, transaction_type])
        )

    @staticmethod
    def get_transactions_for_case_rebuild(case_id):
        return CaseAccessorSQL.get_transactions_by_type(case_id, CaseTransaction.TYPE_FORM)

    @staticmethod
    def case_has_transactions_since_sync(case_id, sync_log_id, sync_log_date):
        with get_cursor(CaseTransaction) as cursor:
            cursor.execute(
                'SELECT case_has_transactions_since_sync(%s, %s, %s)', [case_id, sync_log_id, sync_log_date]
            )
            result = cursor.fetchone()[0]
            return result

    @staticmethod
    def get_case_by_location(domain, location_id):
        try:
            return CommCareCaseSQL.objects.raw(
                'SELECT * from get_case_by_location_id(%s, %s)',
                [domain, location_id]
            )[0]
        except IndexError:
            return None

    @staticmethod
    def get_case_ids_in_domain(domain, type_=None):
        return CaseAccessorSQL._get_case_ids_in_domain(domain, case_type=type_)

    @staticmethod
    def get_deleted_case_ids_in_domain(domain):
        return CaseAccessorSQL._get_case_ids_in_domain(domain, deleted=True)

    @staticmethod
    def get_case_ids_in_domain_by_owners(domain, owner_ids, closed=None):
        return CaseAccessorSQL._get_case_ids_in_domain(domain, owner_ids=owner_ids, is_closed=closed)

    @staticmethod
    def save_case(case):
        transactions_to_save = case.get_live_tracked_models(CaseTransaction)

        indices_to_save_or_update = case.get_live_tracked_models(CommCareCaseIndexSQL)
        index_ids_to_delete = [index.id for index in case.get_tracked_models_to_delete(CommCareCaseIndexSQL)]

        attachments_to_save = case.get_tracked_models_to_create(CaseAttachmentSQL)
        attachment_ids_to_delete = [att.id for att in case.get_tracked_models_to_delete(CaseAttachmentSQL)]
        for attachment in attachments_to_save:
            if attachment.is_saved():
                raise CaseSaveError(
                    """Updating attachments is not supported.
                    case id={}, attachment id={}""".format(
                        case.case_id, attachment.attachment_id
                    )
                )

        try:
            with transaction.atomic(using=case.db, savepoint=False):
                case.save()
                for case_transaction in transactions_to_save:
                    case_transaction.save()

                for index in indices_to_save_or_update:
                    index.domain = case.domain  # ensure domain is set on indices
                    update_fields = None
                    if index.is_saved():
                        # prevent changing identifier
                        update_fields = ['referenced_id', 'referenced_type', 'relationship_id']
                    index.save(update_fields=update_fields)

                CommCareCaseIndexSQL.objects.using(case.db).filter(id__in=index_ids_to_delete).delete()

                for attachment in attachments_to_save:
                    attachment.save()

                CaseAttachmentSQL.objects.using(case.db).filter(id__in=attachment_ids_to_delete).delete()

                case.clear_tracked_models()
        except InternalError as e:
            raise CaseSaveError(e)

    @staticmethod
    def get_open_case_ids_for_owner(domain, owner_id):
        return CaseAccessorSQL._get_case_ids_in_domain(domain, owner_ids=[owner_id], is_closed=False)

    @staticmethod
    def get_closed_case_ids_for_owner(domain, owner_id):
        return CaseAccessorSQL._get_case_ids_in_domain(domain, owner_ids=[owner_id], is_closed=True)

    @staticmethod
    def get_open_case_ids_in_domain_by_type(domain, case_type, owner_ids=None):
        return CaseAccessorSQL._get_case_ids_in_domain(
            domain, case_type=case_type, owner_ids=owner_ids, is_closed=False
        )

    @staticmethod
    def _get_case_ids_in_domain(domain, case_type=None, owner_ids=None, is_closed=None, deleted=False):
        owner_ids = list(owner_ids) if owner_ids else None
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id FROM get_case_ids_in_domain(%s, %s, %s, %s, %s)',
                [domain, case_type, owner_ids, is_closed, deleted]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.case_id for result in results]

    @staticmethod
    def get_related_indices(domain, case_ids, exclude_indices):
        assert isinstance(case_ids, list), case_ids
        if not case_ids:
            return []
        return list(CommCareCaseIndexSQL.objects.raw(
            'SELECT * FROM get_related_indices(%s, %s, %s)',
            [domain, case_ids, list(exclude_indices)]))

    @staticmethod
    def get_closed_and_deleted_ids(domain, case_ids):
        assert isinstance(case_ids, list), case_ids
        if not case_ids:
            return []
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id, closed, deleted FROM get_closed_and_deleted_ids(%s, %s)',
                [domain, case_ids]
            )
            return list(fetchall_as_namedtuple(cursor))

    @staticmethod
    def get_modified_case_ids(accessor, case_ids, sync_log):
        assert isinstance(case_ids, list), case_ids
        if not case_ids:
            return []
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id FROM get_modified_case_ids(%s, %s, %s, %s)',
                [accessor.domain, case_ids, sync_log.date, sync_log._id]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.case_id for result in results]

    @staticmethod
    def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date):
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id FROM get_case_ids_modified_with_owner_since(%s, %s, %s)',
                [domain, owner_id, reference_date]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.case_id for result in results]

    @staticmethod
    def get_extension_case_ids(domain, case_ids, include_closed=True):
        """
        Given a base list of case ids, get all ids of all extension cases that reference them
        """
        if not case_ids:
            return []

        extension_case_ids = set()
        for db_name in get_db_aliases_for_partitioned_query():
            query = CommCareCaseIndexSQL.objects.using(db_name).filter(
                domain=domain,
                relationship_id=CommCareCaseIndexSQL.EXTENSION,
                case__deleted=False,
                referenced_id__in=case_ids)
            if not include_closed:
                query = query.filter(case__closed=False)
            extension_case_ids.update(query.values_list('case_id', flat=True))
        return list(extension_case_ids)

    @staticmethod
    def get_last_modified_dates(domain, case_ids):
        """
        Given a list of case IDs, return a dict where the ids are keys and the
        values are the last server modified date of that case.
        """
        if not case_ids:
            return []
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id, server_modified_on FROM get_case_last_modified_dates(%s, %s)',
                [domain, case_ids]
            )
            results = fetchall_as_namedtuple(cursor)
            return {result.case_id: result.server_modified_on for result in results}

    @staticmethod
    def get_cases_by_external_id(domain, external_id, case_type=None):
        return list(CommCareCaseSQL.objects.raw(
            'SELECT * FROM get_case_by_external_id(%s, %s, %s)',
            [domain, external_id, case_type]
        ))

    @staticmethod
    def get_case_by_domain_hq_user_id(domain, user_id, case_type):
        try:
            return CaseAccessorSQL.get_cases_by_external_id(domain, user_id, case_type)[0]
        except IndexError:
            return None

    @staticmethod
    def soft_undelete_cases(domain, case_ids):
        from corehq.form_processor.change_publishers import publish_case_saved

        assert isinstance(case_ids, list)

        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT soft_undelete_cases(%s, %s) as affected_count',
                [domain, case_ids]
            )
            results = fetchall_as_namedtuple(cursor)
            return_value = sum([result.affected_count for result in results])

        for case_ids_chunk in chunked(case_ids, 500):
            cases = CaseAccessorSQL.get_cases(list(case_ids_chunk))
            for case in cases:
                publish_case_saved(case)

        return return_value

    @staticmethod
    def get_deleted_case_ids_by_owner(domain, owner_id):
        return CaseAccessorSQL._get_case_ids_in_domain(domain, owner_ids=[owner_id], deleted=True)

    @staticmethod
    def soft_delete_cases(domain, case_ids, deletion_date=None, deletion_id=None):
        from corehq.form_processor.change_publishers import publish_case_deleted

        assert isinstance(case_ids, list)
        utcnow = datetime.utcnow()
        deletion_date = deletion_date or utcnow
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT soft_delete_cases(%s, %s, %s, %s, %s) as affected_count',
                [domain, case_ids, utcnow, deletion_date, deletion_id]
            )
            results = fetchall_as_namedtuple(cursor)
            affected_count = sum([result.affected_count for result in results])

        for case_id in case_ids:
            publish_case_deleted(domain, case_id)

        return affected_count

    @staticmethod
    def get_case_owner_ids(domain):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        db_aliases = get_db_aliases_for_partitioned_query()
        owner_ids = set()
        for db_alias in db_aliases:
            owner_ids.update(fast_distinct_in_domain(CommCareCaseSQL, 'owner_id', domain, using=db_alias))

        return owner_ids

    @staticmethod
    def get_case_transactions_for_form(form_id, limit_to_cases):
        for db_name, case_ids in split_list_by_db_partition(limit_to_cases):
            resultset = CaseTransaction.objects.using(db_name).filter(
                case_id__in=case_ids, form_id=form_id
            )
            for trans in resultset:
                yield trans

    @staticmethod
    def get_case_transactions_by_case_id(case, updated_xforms=None):
        """
        This fetches all the transactions required to rebuild the case along
        with all the forms for those transactions.

        For any forms that have been updated it replaces the old form
        with the new one.

        :param case_id: ID of case to rebuild
        :param updated_xforms: list of forms that have been changed.
        :return: list of ``CaseTransaction`` objects with their associated forms attached.
        """

        transactions = CaseAccessorSQL.get_transactions_for_case_rebuild(case.case_id)
        CaseAccessorSQL.fetch_case_transaction_forms(case, transactions, updated_xforms)
        return transactions

    @staticmethod
    def fetch_case_transaction_forms(case, transactions, updated_xforms=None):
        """
        Fetches the forms for a list of transactions, caching them onto each transaction

        :param transactions: list of ``CaseTransaction`` objects:
        :param updated_xforms: list of forms that have been changed.
        """

        form_ids = {tx.form_id for tx in transactions if tx.form_id}
        updated_xforms_map = {
            xform.form_id: xform for xform in updated_xforms if not xform.is_deprecated
        } if updated_xforms else {}

        updated_xform_ids = set(updated_xforms_map)
        form_ids_to_fetch = list(form_ids - updated_xform_ids)
        form_load_counter("rebuild_case", case.domain)(len(form_ids_to_fetch))
        xform_map = {
            form.form_id: form
            for form in FormAccessorSQL.get_forms_with_attachments_meta(form_ids_to_fetch)
        }

        forms_missing_transactions = list(updated_xform_ids - form_ids)
        for form_id in forms_missing_transactions:
            # Add in any transactions that aren't already present
            form = updated_xforms_map[form_id]
            case_updates = [update for update in get_case_updates(form) if update.id == case.case_id]
            types = [
                CaseTransaction.type_from_action_type_slug(a.action_type_slug)
                for case_update in case_updates
                for a in case_update.actions
            ]
            modified_on = case_updates[0].guess_modified_on()
            new_transaction = CaseTransaction.form_transaction(case, form, modified_on, types)
            transactions.append(new_transaction)

        def get_form(form_id):
            if form_id in updated_xforms_map:
                return updated_xforms_map[form_id]

            try:
                return xform_map[form_id]
            except KeyError:
                raise XFormNotFound(form_id)

        for case_transaction in transactions:
            if case_transaction.form_id:
                try:
                    case_transaction.cached_form = get_form(case_transaction.form_id)
                except XFormNotFound:
                    logging.error('Form not found during rebuild: %s', case_transaction.form_id)


class LedgerReindexAccessor(ReindexAccessor):

    def __init__(self, domain=None, limit_db_aliases=None):
        super(LedgerReindexAccessor, self).__init__(limit_db_aliases=limit_db_aliases)
        self.domain = domain

    @property
    def model_class(self):
        return LedgerValue

    @property
    def id_field(self):
        slash = Value('/')
        return {
            'ledger_reference': Concat('case_id', slash, 'section_id', slash, 'entry_id')
        }

    def get_doc(self, doc_id):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        ref = UniqueLedgerReference.from_id(doc_id)
        try:
            return LedgerAccessorSQL.get_ledger_value(**ref._asdict())
        except CaseNotFound:
            pass

    def extra_filters(self, for_count=False):
        if self.domain:
            return [Q(domain=self.domain)]
        return []

    def doc_to_json(self, doc):
        json_doc = doc.to_json()
        json_doc['_id'] = doc.ledger_reference.as_id()
        return json_doc


class LedgerAccessorSQL(AbstractLedgerAccessor):

    @staticmethod
    def get_ledger_values_for_cases(case_ids, section_id=None, entry_id=None, date_start=None, date_end=None):
        assert isinstance(case_ids, list)
        if not case_ids:
            return []

        return list(LedgerValue.objects.raw(
            'SELECT * FROM get_ledger_values_for_cases(%s, %s, %s, %s, %s)',
            [case_ids, section_id, entry_id, date_start, date_end]
        ))

    @staticmethod
    def get_ledger_values_for_case(case_id):
        return list(LedgerValue.objects.raw(
            'SELECT * FROM get_ledger_values_for_cases(%s)',
            [[case_id]]
        ))

    @staticmethod
    def get_ledger_value(case_id, section_id, entry_id):
        try:
            return LedgerValue.objects.raw(
                'SELECT * FROM get_ledger_value(%s, %s, %s)',
                [case_id, section_id, entry_id]
            )[0]
        except IndexError:
            raise LedgerValueNotFound

    @staticmethod
    def save_ledger_values(ledger_values, stock_result=None):
        if not ledger_values and not (stock_result and stock_result.cases_with_deprecated_transactions):
            return

        try:
            if stock_result and stock_result.cases_with_deprecated_transactions:
                db_cases = split_list_by_db_partition(stock_result.cases_with_deprecated_transactions)
                for db_name, case_ids in db_cases:
                    LedgerTransaction.objects.using(db_name).filter(
                        case_id__in=case_ids,
                        form_id=stock_result.xform.form_id
                    ).delete()

            for ledger_value in ledger_values:
                transactions_to_save = ledger_value.get_live_tracked_models(LedgerTransaction)

                with transaction.atomic(using=ledger_value.db, savepoint=False):
                    ledger_value.save()
                    for trans in transactions_to_save:
                        trans.save()

                ledger_value.clear_tracked_models()
        except InternalError as e:
            raise LedgerSaveError(e)

    @staticmethod
    def get_ledger_transactions_for_case(case_id, section_id=None, entry_id=None):
        return list(LedgerTransaction.objects.raw(
            "SELECT * FROM get_ledger_transactions_for_case(%s, %s, %s)",
            [case_id, section_id, entry_id]
        ))

    @staticmethod
    def get_ledger_transactions_in_window(case_id, section_id, entry_id, window_start, window_end):
        return list(LedgerTransaction.objects.raw(
            "SELECT * FROM get_ledger_transactions_for_case(%s, %s, %s, %s, %s)",
            [case_id, section_id, entry_id, window_start, window_end]
        ))

    @staticmethod
    def get_transactions_for_consumption(domain, case_id, product_id, section_id, window_start, window_end):
        from corehq.apps.commtrack.consumption import should_exclude_invalid_periods
        transactions = LedgerAccessorSQL.get_ledger_transactions_in_window(
            case_id, section_id, product_id, window_start, window_end
        )
        exclude_inferred_receipts = should_exclude_invalid_periods(domain)
        return itertools.chain.from_iterable([
            transaction.get_consumption_transactions(exclude_inferred_receipts)
            for transaction in transactions
        ])

    @staticmethod
    def get_latest_transaction(case_id, section_id, entry_id):
        try:
            return LedgerTransaction.objects.raw(
                "SELECT * FROM get_latest_ledger_transaction(%s, %s, %s)",
                [case_id, section_id, entry_id]
            )[0]
        except IndexError:
            return None

    @staticmethod
    def get_current_ledger_state(case_ids, ensure_form_id=False):
        ledger_values = LedgerValue.objects.raw(
            'SELECT * FROM get_ledger_values_for_cases(%s)',
            [case_ids]
        )
        ret = {case_id: {} for case_id in case_ids}
        for value in ledger_values:
            sections = ret[value.case_id].setdefault(value.section_id, {})
            sections[value.entry_id] = value

        return ret

    @staticmethod
    def delete_ledger_transactions_for_form(case_ids, form_id):
        """
        Delete LedgerTransactions for form.
        :param case_ids: list of case IDs which ledger transactions belong to (required for correct sharding)
        :param form_id:  ID of the form
        :return: number of transactions deleted
        """
        assert isinstance(case_ids, list)
        with get_cursor(LedgerTransaction) as cursor:
            cursor.execute(
                "SELECT delete_ledger_transactions_for_form(%s, %s) as deleted_count",
                [case_ids, form_id]
            )
            results = fetchall_as_namedtuple(cursor)
            return sum([result.deleted_count for result in results])

    @staticmethod
    def delete_ledger_values(case_id, section_id=None, entry_id=None):
        """
        Delete LedgerValues marching passed in args
        :param case_id:    ID of the case
        :param section_id: section ID or None
        :param entry_id:   entry ID or None
        :return: number of values deleted
        """
        try:
            with get_cursor(LedgerValue) as cursor:
                cursor.execute(
                    "SELECT delete_ledger_values(%s, %s, %s) as deleted_count",
                    [case_id, section_id, entry_id]
                )
                results = fetchall_as_namedtuple(cursor)
                return sum([result.deleted_count for result in results])
        except InternalError as e:
            raise LedgerSaveError(e)

    @staticmethod
    def get_ledger_transactions_for_form(form_id, limit_to_cases):
        for db_name, case_ids in split_list_by_db_partition(limit_to_cases):
            resultset = LedgerTransaction.objects.using(db_name).filter(
                case_id__in=case_ids, form_id=form_id
            )
            for trans in resultset:
                yield trans


def _sort_with_id_list(object_list, id_list, id_property):
    """Sort object list in the same order as given list of ids

    SQL does not necessarily return the rows in any particular order so
    we need to order them ourselves.

    NOTE: this does not return the sorted list. It sorts `object_list`
    in place using Python's built-in `list.sort`.
    """
    def key(obj):
        return index_map[getattr(obj, id_property)]

    index_map = {id_: index for index, id_ in enumerate(id_list)}
    object_list.sort(key=key)


def _attach_prefetch_models(objects_by_id, prefetched_models, link_field_name, cached_attrib_name):
    prefetched_groups = groupby(prefetched_models, lambda x: getattr(x, link_field_name))
    for obj_id, group in prefetched_groups:
        obj = objects_by_id[obj_id]
        setattr(obj, cached_attrib_name, list(group))
