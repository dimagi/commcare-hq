import logging
from itertools import groupby

from django.db import connection, InternalError
from django.db.models import Q
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound, AttachmentNotFound, CaseSaveError
from corehq.form_processor.interfaces.dbaccessors import AbstractCaseAccessor, AbstractFormAccessor, \
    CaseIndexInfo
from corehq.form_processor.models import (
    XFormInstanceSQL, CommCareCaseIndexSQL, CaseAttachmentSQL, CaseTransaction,
    CommCareCaseSQL, XFormAttachmentSQL, XFormOperationSQL,
    CommCareCaseIndexSQL_DB_TABLE, CaseAttachmentSQL_DB_TABLE)
from corehq.form_processor.utils.sql import fetchone_as_namedtuple, fetchall_as_namedtuple, case_adapter, \
    case_transaction_adapter, case_index_adapter, case_attachment_adapter
from corehq.util.test_utils import unit_testing_only

doc_type_to_state = {
    "XFormInstance": XFormInstanceSQL.NORMAL,
    "XFormError": XFormInstanceSQL.ERROR,
    "XFormDuplicate": XFormInstanceSQL.DUPLICATE,
    "XFormDeprecated": XFormInstanceSQL.DEPRECATED,
    "XFormArchived": XFormInstanceSQL.ARCHIVED,
    "SubmissionErrorLog": XFormInstanceSQL.SUBMISSION_ERROR_LOG
}


class FormAccessorSQL(AbstractFormAccessor):

    @staticmethod
    def get_form(form_id):
        try:
            return XFormInstanceSQL.objects.raw('SELECT * from get_form_by_id(%s)', [form_id])[0]
        except IndexError:
            raise XFormNotFound

    @staticmethod
    def get_forms(form_ids, ordered=False):
        assert isinstance(form_ids, list)
        forms = list(XFormInstanceSQL.objects.raw('SELECT * from get_forms_by_id(%s)', [form_ids]))
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
    def get_form_operations(form_id):
        return list(XFormOperationSQL.objects.raw('SELECT * from get_form_operations(%s)', [form_id]))

    @staticmethod
    def get_forms_with_attachments_meta(form_ids, ordered=False):
        assert isinstance(form_ids, list)
        forms = FormAccessorSQL.get_forms(form_ids)

        # attachments are already sorted by form_id in SQL
        attachments = XFormAttachmentSQL.objects.raw(
            'SELECT * from get_mulitple_forms_attachments(%s)',
            [form_ids]
        )

        forms_by_id = {form.form_id: form for form in forms}
        _attach_prefetch_models(forms_by_id, attachments, 'form_id', 'cached_attachments')

        if ordered:
            _order_list(form_ids, forms, 'form_id')

        return forms

    @staticmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        state = doc_type_to_state[type_]
        assert limit is not None
        return list(XFormInstanceSQL.objects.raw(
            'SELECT * from get_forms_by_state(%s, %s, %s, %s)',
            [domain, state, limit, recent_first]
        ))

    @staticmethod
    def form_with_id_exists(form_id, domain=None):
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM check_form_exists(%s, %s)', [form_id, domain])
            result = fetchone_as_namedtuple(cursor)
            return result.form_exists

    @staticmethod
    def hard_delete_forms(domain, form_ids):
        assert isinstance(form_ids, list)
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM hard_delete_forms(%s, %s)', [domain, form_ids])
            result = fetchone_as_namedtuple(cursor)
            return result.deleted_count

    @staticmethod
    def archive_form(form_id, user_id=None):
        FormAccessorSQL._archive_unarchive_form(form_id, user_id, True)

    @staticmethod
    def unarchive_form(form_id, user_id=None):
        FormAccessorSQL._archive_unarchive_form(form_id, user_id, False)

    @staticmethod
    def _archive_unarchive_form(form_id, user_id, archive):
        with connection.cursor() as cursor:
            cursor.execute('SELECT archive_unarchive_form(%s, %s, %s)', [form_id, user_id, archive])
            cursor.execute('SELECT revoke_restore_case_transactions_for_form(%s, %s)', [form_id, archive])

    @staticmethod
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
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT form_pk FROM save_new_form_with_attachments(%s, %s)',
                [form, unsaved_attachments]
            )
            result = fetchone_as_namedtuple(cursor)
            form.id = result.form_pk

    @staticmethod
    def save_deprecated_form(form):
        assert form.is_saved(), "Can't deprecate an unsaved form"
        assert form.is_deprecated, 'Re-saving already saved forms not supported'
        assert getattr(form, 'unsaved_attachments', None) is None, \
            'Adding attachments to saved form not supported'

        logging.debug('Deprecating form: %s', form)

        with connection.cursor() as cursor:
            cursor.execute('SELECT deprecate_form(%s, %s, %s)', [form.form_id, form.orig_id, form.edited_on])

    @staticmethod
    def update_form_problem_and_state(form):
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT update_form_problem_and_state(%s, %s, %s)',
                [form.form_id, form.problem, form.state]
            )

    @staticmethod
    @unit_testing_only
    def get_form_ids_in_domain(domain, user_id=None):
        with connection.cursor() as cursor:
            cursor.execute('SELECT form_id FROM get_form_ids_in_domain(%s, %s)', [domain, user_id])
            results = fetchall_as_namedtuple(cursor)
            return [result.form_id for result in results]


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
        cases = list(CommCareCaseSQL.objects.raw('SELECT * from get_cases_by_id(%s)', [case_ids]))
        if ordered:
            cases = _order_list(case_ids, cases, 'case_id')

        return cases

    @staticmethod
    def case_modified_since(case_id, server_modified_on):
        """
        Return True if a case has been modified since the given modification date.
        Assumes that the case exists in the DB.
        """
        with connection.cursor() as cursor:
            cursor.execute('SELECT case_modified FROM case_modified_since(%s, %s)', [case_id, server_modified_on])
            result = fetchone_as_namedtuple(cursor)
            return result.case_modified

    @staticmethod
    def get_case_xform_ids(case_id):
        with connection.cursor() as cursor:
            cursor.execute('SELECT form_id FROM get_case_form_ids(%s)', [case_id])
            results = fetchall_as_namedtuple(cursor)
            return [result.form_id for result in results]

    @staticmethod
    def get_indices(case_id):
        return list(CommCareCaseIndexSQL.objects.raw('SELECT * FROM get_case_indices(%s)', [case_id]))

    @staticmethod
    def get_reverse_indices(case_id):
        return list(CommCareCaseIndexSQL.objects.raw('SELECT * FROM get_case_indices_reverse(%s)', [case_id]))

    @staticmethod
    def get_all_reverse_indices_info(domain, case_ids):
        query = CommCareCaseIndexSQL.objects.filter(
            # domain=domain,  # TODO: Why isn't domain being saved on CommCareCaseIndexSQL objects?
            referenced_id__in=case_ids
        )
        return [
            CaseIndexInfo(
                case_id=index.case_id,
                identifier=index.identifier,
                referenced_id=index.referenced_id,
                referenced_type=index.referenced_type,
                relationship=index.relationship_id
            ) for index in query
        ]

    @staticmethod
    def get_indexed_case_ids(domain, case_ids):
        """
        Given a base list of case ids, gets all ids of cases they reference (parent and host cases)
        """
        query = CommCareCaseIndexSQL.objects.filter(
            # domain=domain,  # TODO: Why isn't domain being saved on CommCareCaseIndexSQL objects?
            case_id__in=case_ids
        )
        return list(set(query.values_list('referenced_id', flat=True)))

    @staticmethod
    def get_reverse_indexed_cases(domain, case_ids):
        assert isinstance(case_ids, list)

        cases = list(CommCareCaseSQL.objects.raw(
            'SELECT * FROM get_reverse_indexed_cases(%s, %s)',
            [domain, case_ids])
        )
        cases_by_id = {case.case_id: case for case in cases}
        indices = list(CommCareCaseIndexSQL.objects.raw(
            'SELECT * FROM get_multiple_cases_indices(%s)',
            [cases_by_id.keys()])
        )
        _attach_prefetch_models(cases_by_id, indices, 'case_id', 'cached_indices')
        return cases

    @staticmethod
    def hard_delete_cases(domain, case_ids):
        assert isinstance(case_ids, list)
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM hard_delete_cases(%s, %s)', [domain, case_ids])
            result = fetchone_as_namedtuple(cursor)
            return result.deleted_count

    @staticmethod
    def get_attachment_by_name(case_id, attachment_name):
        try:
            return CommCareCaseSQL.objects.raw(
                'select * from get_case_attachment_by_name(%s, %s)',
                [case_id, attachment_name]
            )[0]
        except IndexError:
            raise AttachmentNotFound(attachment_name)

    @staticmethod
    def get_attachments(case_id):
        return list(CaseAttachmentSQL.objects.raw('SELECT * from get_case_attachments(%s)', [case_id]))

    @staticmethod
    def get_transactions(case_id):
        return list(CaseTransaction.objects.raw('SELECT * from get_case_transactions(%s)', [case_id]))

    @staticmethod
    def get_transactions_for_case_rebuild(case_id):
        return list(CaseTransaction.objects.raw(
            'SELECT * from get_case_transactions_for_rebuild(%s)',
            [case_id])
        )

    @staticmethod
    def case_has_transactions_since_sync(case_id, sync_log_id, sync_log_date):
        query = CaseTransaction.objects.filter(
            case_id=case_id,
            server_date__gt=sync_log_date,
        ).exclude(
            sync_log_id=sync_log_id
        )
        return query.exists()

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
        with connection.cursor() as cursor:
            cursor.execute('SELECT case_id FROM get_case_ids_in_domain(%s, %s)', [domain, type_])
            results = fetchall_as_namedtuple(cursor)
            return [result.case_id for result in results]

    @staticmethod
    def get_case_ids_in_domain_by_owners(domain, owner_ids):
        query = CommCareCaseSQL.objects.filter(
            domain=domain,
            owner_id__in=owner_ids,
        )
        return list(query.values_list('case_id', flat=True))

    @staticmethod
    def save_case(case):
        transactions_to_save = case.get_tracked_models_to_create(CaseTransaction)

        indices_to_save_or_update = case.get_tracked_models_to_create(CommCareCaseIndexSQL)
        indices_to_save_or_update.extend(case.get_tracked_models_to_update(CommCareCaseIndexSQL))
        index_ids_to_delete = [index.id for index in case.get_tracked_models_to_delete(CommCareCaseIndexSQL)]

        attachments_to_save = case.get_tracked_models_to_create(CaseAttachmentSQL)
        attachment_ids_to_delete = [att.id for att in case.get_tracked_models_to_delete(CaseAttachmentSQL)]

        # cast arrays that can be empty to appropriate type
        query = """SELECT case_pk FROM save_case_and_related_models(
            %s, %s, %s::{}[], %s::{}[], %s::INTEGER[], %s::INTEGER[]
        )"""
        query = query.format(CommCareCaseIndexSQL_DB_TABLE, CaseAttachmentSQL_DB_TABLE)
        with connection.cursor() as cursor:
            try:
                cursor.execute(query, [
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

    @staticmethod
    def get_open_case_ids(domain, owner_id):
        owner_id_is_falsey = Q(owner_id=None) | Q(owner_id="")
        owner_query = Q(owner_id=owner_id) | (owner_id_is_falsey & Q(modified_by=owner_id))
        query = CommCareCaseSQL.objects.filter(domain=domain, closed=False).filter(owner_query)
        return list(query.values_list('case_id', flat=True))

    @staticmethod
    def get_closed_case_ids(domain, owner_id):
        query = CommCareCaseSQL.objects.filter(domain=domain, owner_id=owner_id, closed=True)
        return list(query.values_list('case_id', flat=True))

    @staticmethod
    def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date):
        raise NotImplementedError

    @staticmethod
    def get_extension_case_ids(domain, case_ids): # I need like this but without the relationship id check
        """
        Given a base list of case ids, for those that are open, get all ids of all extension cases that reference them
        """
        query = CommCareCaseIndexSQL.objects.filter(
            # domain=domain,  # TODO: Why isn't domain being used?
            referenced_id__in=case_ids,
            relationship_id=CommCareCaseIndexSQL.EXTENSION
        )
        # TODO: Filter by open cases?
        return list(query.values_list('case_id', flat=True))

    @staticmethod
    def get_last_modified_dates(domain, case_ids):
        """
        Given a list of case IDs, return a dict where the ids are keys and the
        values are the last server modified date of that case.
        """
        query = CommCareCaseSQL.objects.filter(
            domain=domain,
            case_id__in=case_ids
        )
        return dict(query.values_list("case_id", "server_modified_on"))


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

