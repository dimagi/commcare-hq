import logging
from abc import ABCMeta, abstractproperty
from abc import abstractmethod
from itertools import groupby
from datetime import datetime

import itertools

import six
from django.conf import settings
from django.db import connections, InternalError, transaction

from corehq.form_processor.exceptions import (
    XFormNotFound,
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
    XFormAttachmentSQL,
    XFormOperationSQL,
    CommCareCaseIndexSQL_DB_TABLE,
    CaseAttachmentSQL_DB_TABLE,
    LedgerTransaction_DB_TABLE,
    LedgerValue_DB_TABLE,
    LedgerValue,
    LedgerTransaction,
)
from corehq.form_processor.utils.sql import (
    fetchone_as_namedtuple,
    fetchall_as_namedtuple,
    case_adapter,
    case_transaction_adapter,
    case_index_adapter,
    case_attachment_adapter
)
from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only

doc_type_to_state = {
    "XFormInstance": XFormInstanceSQL.NORMAL,
    "XFormError": XFormInstanceSQL.ERROR,
    "XFormDuplicate": XFormInstanceSQL.DUPLICATE,
    "XFormDeprecated": XFormInstanceSQL.DEPRECATED,
    "XFormArchived": XFormInstanceSQL.ARCHIVED,
    "SubmissionErrorLog": XFormInstanceSQL.SUBMISSION_ERROR_LOG
}


def get_cursor(model):
    db = db_for_read_write(model)
    return connections[db].cursor()


class ReindexAccessor(six.with_metaclass(ABCMeta)):

    @abstractproperty
    def startkey_attribute_name(self):
        """
        :return: The name of the attribute to filter successive batches by e.g. 'received_on'
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

    @abstractmethod
    def get_docs(self, from_db, startkey, last_doc_pk=None, limit=500):
        """Get a batch of
        :param from_db: The DB alias to query
        :param startkey: The filter value to start from e.g. form.received_on
        :param last_doc_pk: The primary key of the last doc from the previous batch
        :param limit: Desired batch size
        :return: List of documents
        """
        raise NotImplementedError


class FormReindexAccessor(ReindexAccessor):

    @property
    def startkey_attribute_name(self):
        return 'received_on'

    def get_doc(self, doc_id):
        try:
            return FormAccessorSQL.get_form(doc_id)
        except XFormNotFound:
            pass

    def doc_to_json(self, doc):
        from corehq.form_processor.utils.xform import add_couch_properties_to_sql_form_json
        return add_couch_properties_to_sql_form_json(
            doc.to_json(include_attachments=True)
        )

    def get_docs(self, from_db, startkey, last_doc_pk=None, limit=500):
        received_on_since = startkey or datetime.min
        last_id = last_doc_pk or -1
        results = XFormInstanceSQL.objects.raw(
            'SELECT * FROM get_all_forms_received_since(%s, %s, %s)',
            [received_on_since, last_id, limit],
            using=from_db
        )
        # note: in memory sorting and limit not necessary since we're only queyring a single DB
        return RawQuerySetWrapper(results)


class FormAccessorSQL(AbstractFormAccessor):

    @staticmethod
    def get_form(form_id):
        try:
            return FormAccessorSQL.get_forms([form_id])[0]
        except IndexError:
            raise XFormNotFound

    @staticmethod
    def get_forms(form_ids, ordered=False):
        assert isinstance(form_ids, list)
        forms = RawQuerySetWrapper(XFormInstanceSQL.objects.raw('SELECT * from get_forms_by_id(%s)', [form_ids]))
        if ordered:
            forms = _order_list(form_ids, forms, 'form_id')

        return forms

    @staticmethod
    def get_attachments(form_id):
        return list(XFormAttachmentSQL.objects.raw('SELECT * from get_form_attachments(%s)', [form_id]))

    @staticmethod
    def get_with_attachments(form_id):
        """
        It's necessary to store these on the form rather than use a memoized property
        since the form_id can change (in the case of a deprecated form) which breaks
        the memoize hash.
        """
        form = FormAccessorSQL.get_form(form_id)
        attachments = FormAccessorSQL.get_attachments(form_id)
        form.cached_attachments = attachments
        return form

    @staticmethod
    def get_attachment_by_name(form_id, attachment_name):
        try:
            return XFormAttachmentSQL.objects.raw(
                'select * from get_form_attachment_by_name(%s, %s)',
                [form_id, attachment_name]
            )[0]
        except IndexError:
            raise AttachmentNotFound(attachment_name)

    @staticmethod
    def get_attachment_content(form_id, attachment_name, stream=False):
        meta = FormAccessorSQL.get_attachment_by_name(form_id, attachment_name)
        return AttachmentContent(meta.content_type, meta.read_content(stream=True))

    @staticmethod
    def get_form_operations(form_id):
        return list(XFormOperationSQL.objects.raw('SELECT * from get_form_operations(%s)', [form_id]))

    @staticmethod
    def get_forms_with_attachments_meta(form_ids, ordered=False):
        assert isinstance(form_ids, list)
        forms = list(FormAccessorSQL.get_forms(form_ids))

        # attachments are already sorted by form_id in SQL
        attachments = XFormAttachmentSQL.objects.raw(
            'SELECT * from get_multiple_forms_attachments(%s)',
            [form_ids]
        )

        forms_by_id = {form.form_id: form for form in forms}
        _attach_prefetch_models(forms_by_id, attachments, 'form_id', 'cached_attachments')

        if ordered:
            forms = _order_list(form_ids, forms, 'form_id')

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
    @transaction.atomic
    def hard_delete_forms(domain, form_ids):
        assert isinstance(form_ids, list)
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute('SELECT hard_delete_forms(%s, %s) AS deleted_count', [domain, form_ids])
            results = fetchall_as_namedtuple(cursor)
            return sum([result.deleted_count for result in results])

    @staticmethod
    def archive_form(form, user_id=None):
        from corehq.form_processor.change_publishers import publish_form_saved
        FormAccessorSQL._archive_unarchive_form(form, user_id, True)
        form.state = XFormInstanceSQL.ARCHIVED
        publish_form_saved(form)

    @staticmethod
    def unarchive_form(form, user_id=None):
        from corehq.form_processor.change_publishers import publish_form_saved
        FormAccessorSQL._archive_unarchive_form(form, user_id, False)
        form.state = XFormInstanceSQL.NORMAL
        publish_form_saved(form)

    @staticmethod
    def soft_undelete_forms(domain, form_ids):
        assert isinstance(form_ids, list)
        problem = 'Restored on {}'.format(datetime.utcnow())
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT soft_undelete_forms(%s, %s, %s) as affected_count',
                [domain, form_ids, problem]
            )
            results = fetchall_as_namedtuple(cursor)
            return sum([result.affected_count for result in results])

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
            cursor.execute('SELECT revoke_restore_case_transactions_for_form(%s, %s, %s)', [case_ids, form_id, archive])

    @staticmethod
    @transaction.atomic
    def save_new_form(form):
        """
        Save a previously unsaved form
        """
        assert not form.is_saved(), 'form already saved'
        logging.debug('Saving new form: %s', form)
        unsaved_attachments = getattr(form, 'unsaved_attachments', [])
        if unsaved_attachments:
            del form.unsaved_attachments
            for unsaved_attachment in unsaved_attachments:
                unsaved_attachment.form = form

        operations = form.get_tracked_models_to_create(XFormOperationSQL)
        for operation in operations:
            operation.form = form
        form.clear_tracked_models()

        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT form_pk FROM save_new_form_and_related_models(%s, %s, %s, %s)',
                [form.form_id, form, unsaved_attachments, operations]
            )
            result = fetchone_as_namedtuple(cursor)
            form.id = result.form_pk

    @staticmethod
    @transaction.atomic
    def save_deprecated_form(form):
        assert form.is_saved(), "Can't deprecate an unsaved form"
        assert form.is_deprecated, 'Re-saving already saved forms not supported'
        assert getattr(form, 'unsaved_attachments', None) is None, \
            'Adding attachments to saved form not supported'

        logging.debug('Deprecating form: %s', form)

        attachments = form.get_attachments()
        operations = form.history

        form.id = None
        for attachment in attachments:
            attachment.id = None
        form.unsaved_attachments = attachments

        for operation in operations:
            operation.id = None
            form.track_create(operation)

        deleted = FormAccessorSQL.hard_delete_forms(form.domain, [form.orig_id])
        assert deleted == 1
        FormAccessorSQL.save_new_form(form)

    @staticmethod
    @transaction.atomic
    def update_form_problem_and_state(form):
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute(
                'SELECT update_form_problem_and_state(%s, %s, %s)',
                [form.form_id, form.problem, form.state]
            )

    @staticmethod
    @unit_testing_only
    @transaction.atomic
    def delete_all_forms(domain=None, user_id=None):
        with get_cursor(XFormInstanceSQL) as cursor:
            cursor.execute('SELECT delete_all_forms(%s, %s)', [domain, user_id])

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

    @staticmethod
    def get_all_forms_received_since(received_on_since=None, chunk_size=500):
        """Iterate through all forms in the entire database, optionally received since
        a specific date
        """

        return _batch_iterate_over_shards(
            batch_fn=FormAccessorSQL._get_forms_received_since,
            next_start_args=lambda form: (form.received_on, form.id),
            start_from=received_on_since,
            chunk_size=chunk_size
        )

    @staticmethod
    def _get_forms_received_since(received_on_since=None, last_id=None, limit=500, using=None):
        """
        Function to be used with ``_batch_iterate_over_shards`` to iterate over all
        forms in the entire database.

        :param using: alternate DB alias to query against
        :return:
        """
        received_on_since = received_on_since or datetime.min
        last_id = last_id or -1
        results = XFormInstanceSQL.objects.raw(
            'SELECT * FROM get_all_forms_received_since(%s, %s, %s)',
            [received_on_since, last_id, limit],
            using=using
        )
        # note: in memory sorting and limit not necessary since we're only queyring a single DB
        return RawQuerySetWrapper(results)


class CaseReindexAccessor(ReindexAccessor):
    @property
    def startkey_attribute_name(self):
        return 'server_modified_on'

    def get_doc(self, doc_id):
        try:
            return CaseAccessorSQL.get_case(doc_id)
        except CaseNotFound:
            pass

    def get_docs(self, from_db, startkey, last_doc_pk=None, limit=500):
        server_modified_on_since = startkey or datetime.min
        last_id = last_doc_pk or -1
        results = CommCareCaseSQL.objects.raw(
            'SELECT * FROM get_all_cases_modified_since(%s, %s, %s)',
            [server_modified_on_since, last_id, limit],
            using=from_db
        )
        # note: in memory sorting and limit not necessary since we're only queyring a single DB
        return RawQuerySetWrapper(results)


class CaseAccessorSQL(AbstractCaseAccessor):

    @staticmethod
    def get_case(case_id):
        try:
            return CommCareCaseSQL.objects.raw('SELECT * from get_case_by_id(%s)', [case_id])[0]
        except IndexError:
            raise CaseNotFound

    @staticmethod
    def get_cases(case_ids, ordered=False):
        assert isinstance(case_ids, list)
        cases = RawQuerySetWrapper(CommCareCaseSQL.objects.raw('SELECT * from get_cases_by_id(%s)', [case_ids]))
        if ordered:
            cases = _order_list(case_ids, cases, 'case_id')

        return cases

    @staticmethod
    def case_modified_since(case_id, server_modified_on):
        """
        Return True if a case has been modified since the given modification date.
        Assumes that the case exists in the DB.
        """
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute('SELECT case_modified FROM case_modified_since(%s, %s)', [case_id, server_modified_on])
            result = fetchone_as_namedtuple(cursor)
            return result.case_modified

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
        with get_cursor(CommCareCaseIndexSQL) as cursor:
            cursor.execute(
                'SELECT referenced_id FROM get_multiple_cases_indices(%s, %s)',
                [domain, list(case_ids)]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.referenced_id for result in results]

    @staticmethod
    def get_reverse_indexed_cases(domain, case_ids):
        assert isinstance(case_ids, list)

        cases = list(CommCareCaseSQL.objects.raw(
            'SELECT * FROM get_reverse_indexed_cases(%s, %s)',
            [domain, case_ids])
        )
        cases_by_id = {case.case_id: case for case in cases}
        indices = list(CommCareCaseIndexSQL.objects.raw(
            'SELECT * FROM get_multiple_cases_indices(%s, %s)',
            [domain, cases_by_id.keys()])
        )
        _attach_prefetch_models(cases_by_id, indices, 'case_id', 'cached_indices')
        return cases

    @staticmethod
    def hard_delete_cases(domain, case_ids):
        assert isinstance(case_ids, list)
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute('SELECT hard_delete_cases(%s, %s) as deleted_count', [domain, case_ids])
            results = fetchall_as_namedtuple(cursor)
            return sum([result.deleted_count for result in results])

    @staticmethod
    def get_attachment_by_identifier(case_id, identifier):
        try:
            return CaseAttachmentSQL.objects.raw(
                'select * from get_case_attachment_by_identifier(%s, %s)',
                [case_id, identifier]
            )[0]
        except IndexError:
            raise AttachmentNotFound(identifier)

    @staticmethod
    def get_attachment_content(case_id, attachment_id):
        meta = CaseAccessorSQL.get_attachment_by_identifier(case_id, attachment_id)
        return AttachmentContent(meta.content_type, meta.read_content(stream=True))

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
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute('SELECT case_id FROM get_case_ids_in_domain(%s, %s)', [domain, type_])
            results = fetchall_as_namedtuple(cursor)
            return [result.case_id for result in results]

    @staticmethod
    def get_case_ids_in_domain_by_owners(domain, owner_ids, closed=None):
        return CaseAccessorSQL._get_case_ids_in_domain(domain, owner_ids=owner_ids, is_closed=closed)

    @staticmethod
    @unit_testing_only
    def delete_all_cases(domain=None):
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute('SELECT delete_all_cases(%s)', [domain])

    @staticmethod
    def get_all_cases_modified_since(server_modified_on_since=None, chunk_size=500):
        """
        Iterate through all cases in the entire database, optionally modified since
        a specific date
        :param server_modified_on_since:
        :param chunk_size:
        :return: generator of cases
        """
        return _batch_iterate_over_shards(
            CaseAccessorSQL._get_cases_modified_since,
            next_start_args=lambda case: (case.server_modified_on, case.id),
            start_from=server_modified_on_since,
            chunk_size=chunk_size
        )

    @staticmethod
    def _get_cases_modified_since(server_modified_on_since=None, last_id=None, limit=500, using=None):
        """
        Function to be used with ``_batch_iterate_over_shards`` to iterate over all
        cases in the entire database.

        :param using: alternate DB alias to query against
        :return:
        """
        server_modified_on_since = server_modified_on_since or datetime.min
        last_id = last_id or -1
        results = CommCareCaseSQL.objects.raw(
            'SELECT * FROM get_all_cases_modified_since(%s, %s, %s)',
            [server_modified_on_since, last_id, limit],
            using=using
        )
        # note: in memory sorting and limit not necessary since we're only queyring a single DB
        return RawQuerySetWrapper(results)

    @staticmethod
    @transaction.atomic
    def save_case(case):
        transactions_to_save = case.get_tracked_models_to_create(CaseTransaction)

        indices_to_save_or_update = case.get_tracked_models_to_create(CommCareCaseIndexSQL)
        indices_to_save_or_update.extend(case.get_tracked_models_to_update(CommCareCaseIndexSQL))
        index_ids_to_delete = [index.id for index in case.get_tracked_models_to_delete(CommCareCaseIndexSQL)]

        attachments_to_save = case.get_tracked_models_to_create(CaseAttachmentSQL)
        attachment_ids_to_delete = [att.id for att in case.get_tracked_models_to_delete(CaseAttachmentSQL)]

        for index in indices_to_save_or_update:
            index.domain = case.domain  # ensure domain is set on indices

        # cast arrays that can be empty to appropriate type
        query = """SELECT case_pk FROM save_case_and_related_models(
            %s, %s, %s, %s::{}[], %s::{}[], %s::INTEGER[], %s::INTEGER[]
        )"""
        query = query.format(CommCareCaseIndexSQL_DB_TABLE, CaseAttachmentSQL_DB_TABLE)
        with get_cursor(CommCareCaseSQL) as cursor:
            try:
                cursor.execute(query, [
                    case.case_id,
                    case,
                    transactions_to_save,
                    indices_to_save_or_update,
                    attachments_to_save,
                    index_ids_to_delete,
                    attachment_ids_to_delete
                ])
                result = fetchone_as_namedtuple(cursor)
                case.id = result.case_pk
                case.clear_tracked_models()
            except InternalError as e:
                if logging.root.isEnabledFor(logging.DEBUG):
                    msg = 'save_case_and_related_models called with args: \n{}, {}, {}, {} ,{} ,{}'.format(
                        case_adapter(case).getquoted(),
                        [case_transaction_adapter(t).getquoted() for t in transactions_to_save],
                        [case_index_adapter(i).getquoted() for i in indices_to_save_or_update],
                        [case_attachment_adapter(a).getquoted() for a in attachments_to_save],
                        index_ids_to_delete,
                        attachment_ids_to_delete
                    )
                    logging.debug(msg)
                raise CaseSaveError(e)
            else:
                for attachment in case.get_tracked_models_to_delete(CaseAttachmentSQL):
                    attachment.delete_content()

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
    def _get_case_ids_in_domain(domain, case_type=None, owner_ids=None, is_closed=None):
        owner_ids = list(owner_ids) if owner_ids else None
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id FROM get_case_ids_in_domain(%s, %s, %s, %s)',
                [domain, case_type, owner_ids, is_closed]
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
    def get_extension_case_ids(domain, case_ids):
        """
        Given a base list of case ids, get all ids of all extension cases that reference them
        """
        with get_cursor(CommCareCaseIndexSQL) as cursor:
            cursor.execute('SELECT case_id FROM get_extension_case_ids(%s, %s)', [domain, list(case_ids)])
            results = fetchall_as_namedtuple(cursor)
            return [result.case_id for result in results]

    @staticmethod
    def get_last_modified_dates(domain, case_ids):
        """
        Given a list of case IDs, return a dict where the ids are keys and the
        values are the last server modified date of that case.
        """
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id, server_modified_on FROM get_case_last_modified_dates(%s, %s)',
                [domain, case_ids]
            )
            results = fetchall_as_namedtuple(cursor)
            return dict((result.case_id, result.server_modified_on) for result in results)

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
    def get_case_types_for_domain(domain):
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_type FROM get_case_types_for_domain(%s)',
                [domain]
            )
            results = fetchall_as_namedtuple(cursor)
            return {result.case_type for result in results}

    @staticmethod
    def soft_undelete_cases(domain, case_ids):
        assert isinstance(case_ids, list)

        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT soft_undelete_cases(%s, %s) as affected_count',
                [domain, case_ids]
            )
            results = fetchall_as_namedtuple(cursor)
            return sum([result.affected_count for result in results])

    @staticmethod
    def get_deleted_case_ids_by_owner(domain, owner_id):
        with get_cursor(CommCareCaseSQL) as cursor:
            cursor.execute(
                'SELECT case_id FROM get_deleted_case_ids_by_owner(%s, %s)',
                [domain, owner_id]
            )
            results = fetchall_as_namedtuple(cursor)
            return [result.case_id for result in results]

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


class LedgerReindexAccessor(ReindexAccessor):
    @property
    def startkey_attribute_name(self):
        return 'last_modified'

    def get_doc(self, doc_id):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        ref = UniqueLedgerReference.from_id(doc_id)
        try:
            return LedgerAccessorSQL.get_ledger_value(**ref._asdict())
        except CaseNotFound:
            pass

    def get_docs(self, from_db, startkey, last_doc_pk=None, limit=500):
        modified_since = startkey or datetime.min
        last_id = last_doc_pk or -1
        results = LedgerValue.objects.raw(
            'SELECT * FROM get_all_ledger_values_modified_since(%s, %s, %s)',
            [modified_since, last_id, limit],
            using=from_db
        )
        # note: in memory sorting and limit not necessary since we're only queyring a single DB
        return RawQuerySetWrapper(results)

    def doc_to_json(self, doc):
        json_doc = doc.to_json()
        json_doc['_id'] = doc.ledger_reference.as_id()
        return json_doc


class LedgerAccessorSQL(AbstractLedgerAccessor):

    @staticmethod
    def get_ledger_values_for_cases(case_ids, section_id=None, entry_id=None, date_start=None, date_end=None):
        assert isinstance(case_ids, list)
        return RawQuerySetWrapper(LedgerValue.objects.raw(
            'SELECT * FROM get_ledger_values_for_cases(%s, %s, %s, %s, %s)',
            [case_ids, section_id, entry_id, date_start, date_end]
        ))

    @staticmethod
    def get_all_ledgers_modified_since(modified_since=None, chunk_size=500):
        """
        Iterate through all ledger_values in the entire database, optionally modified since
        a specific date
        """
        return _batch_iterate_over_shards(
            batch_fn=LedgerAccessorSQL._get_ledgers_modified_since,
            next_start_args=lambda ledger: (ledger.last_modified, ledger.id),
            start_from=modified_since,
            chunk_size=chunk_size
        )

    @staticmethod
    def _get_ledgers_modified_since(modified_since=None, last_id=None, limit=500, using=None):
        """
        Function to be used with ``_batch_iterate_over_shards`` to iterate over all
        ledgers in the entire database.

        :param using: alternate DB alias to query against
        :return:
        """
        modified_since = modified_since or datetime.min
        last_id = last_id or -1
        results = LedgerValue.objects.raw(
            'SELECT * FROM get_all_ledger_values_modified_since(%s, %s, %s)',
            [modified_since, last_id, limit],
            using=using
        )
        # note: in memory sorting and limit not necessary since we're only queyring a single DB
        return RawQuerySetWrapper(results)

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
    def save_ledger_values(ledger_values, deprecated_form=None):
        if not ledger_values:
            return

        deprecated_form_id = deprecated_form.orig_id if deprecated_form else None

        for ledger_value in ledger_values:
            transactions_to_save = ledger_value.get_live_tracked_models(LedgerTransaction)

            with get_cursor(LedgerValue) as cursor:
                try:
                    cursor.execute(
                        "SELECT save_ledger_values(%s, %s::{}, %s::{}[], %s)".format(
                            LedgerValue_DB_TABLE,
                            LedgerTransaction_DB_TABLE
                        ),
                        [ledger_value.case_id, ledger_value, transactions_to_save, deprecated_form_id]
                    )
                except InternalError as e:
                    raise LedgerSaveError(e)

            ledger_value.clear_tracked_models()

    @staticmethod
    def get_ledger_transactions_for_case(case_id, section_id=None, entry_id=None):
        return RawQuerySetWrapper(LedgerTransaction.objects.raw(
            "SELECT * FROM get_ledger_transactions_for_case(%s, %s, %s)",
            [case_id, section_id, entry_id]
        ))

    @staticmethod
    def get_ledger_transactions_in_window(case_id, section_id, entry_id, window_start, window_end):
        return RawQuerySetWrapper(LedgerTransaction.objects.raw(
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


def _order_list(id_list, object_list, id_property):
    # SQL won't return the rows in any particular order so we need to order them ourselves
    index_map = {id_: index for index, id_ in enumerate(id_list)}
    ordered_list = [None] * len(id_list)
    for obj in object_list:
        ordered_list[index_map[getattr(obj, id_property)]] = obj

    return ordered_list


def _attach_prefetch_models(objects_by_id, prefetched_models, link_field_name, cached_attrib_name):
    prefetched_groups = groupby(prefetched_models, lambda x: getattr(x, link_field_name))
    for obj_id, group in prefetched_groups:
        obj = objects_by_id[obj_id]
        setattr(obj, cached_attrib_name, list(group))


def _batch_iterate_over_shards(batch_fn, next_start_args, start_from=None, chunk_size=500):
    """
    Iterate through a function in batches. Assumes the following signatures:

    batch_fn(start_from, last_id, limit=limit, using=db_alias) - a function that returns sorted data in batches
    next_start_args(item) - a function that returns a tuple of "start_from" and "last_id" for the next batch.
    The key is used to exclude duplicate items.
    """
    # TODO: implement this https://wiki.postgresql.org/images/3/35/Pagination_Done_the_PostgreSQL_Way.pdf
    start_from = start_from or datetime.min
    if not settings.USE_PARTITIONED_DATABASE:
        db_list = [None]  # use the default database
    else:
        from corehq.sql_db.config import PartitionConfig
        partition_config = PartitionConfig()
        db_list = partition_config.get_form_processing_dbs()

    db_status = {db: {'start_from': start_from, 'last_id': None, 'has_more': True} for db in db_list}

    has_more = True
    while has_more:
        for db_alias in db_list:
            if not db_status[db_alias]['has_more']:
                continue

            db_start_from = db_status[db_alias]['start_from']
            last_id = db_status[db_alias]['last_id']
            batch = batch_fn(db_start_from, last_id, limit=chunk_size, using=db_alias)
            batch_size = len(batch)

            for item in batch:
                yield item

            if batch_size == chunk_size:
                # we got a full chunk so keep checking for more
                next_start_from, next_last_id = next_start_args(item)
                assert next_start_from > db_start_from  # make sure we are making progress
                db_status[db_alias]['start_from'] = next_start_from
                db_status[db_alias]['last_id'] = next_last_id
            else:
                db_status[db_alias]['has_more'] = False

        has_more = any(status['has_more'] for status in db_status.values())


class RawQuerySetWrapper(object):
    """
    Wrapper for RawQuerySet objects to make them behave more like
    normal QuerySet objects
    """

    def __init__(self, queryset):
        self.queryset = queryset
        self._result_cache = None

    def _fetch_all(self):
        if self._result_cache is None:
            self._result_cache = list(self.queryset)
        return self._result_cache

    def __getattr__(self, item):
        return getattr(self.queryset, item)

    def __getitem__(self, k):
        self._fetch_all()
        return list(self._result_cache)[k]

    def __iter__(self):
        return self.queryset.__iter__()

    def __len__(self):
        self._fetch_all()
        return len(self._result_cache)

    def __nonzero__(self):
        self._fetch_all()
        return bool(self._result_cache)
