from datetime import datetime
from django.db import transaction
from django.db.models import Prefetch
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import AbstractCaseAccessor, AbstractFormAccessor
from corehq.form_processor.models import (
    XFormInstanceSQL, CommCareCaseIndexSQL, CaseAttachmentSQL, CaseTransaction,
    CommCareCaseSQL, XFormAttachmentSQL, XFormOperationSQL
)

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
            return XFormInstanceSQL.objects.get(form_uuid=form_id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @staticmethod
    def get_with_attachments(form_id):
        try:
            return XFormInstanceSQL.objects.prefetch_related(
                Prefetch('attachments', to_attr='cached_attachments')
            ).get(form_uuid=form_id)
        except XFormInstanceSQL.DoesNotExist:
            raise XFormNotFound

    @staticmethod
    def get_forms_with_attachments_meta(form_ids):
        return XFormInstanceSQL.objects.prefetch_related(
            Prefetch('attachments', to_attr='cached_attachments')
        ).filter(form_uuid__in=form_ids)

    @staticmethod
    def get_forms_by_type(domain, type_, recent_first=False, limit=None):
        state = doc_type_to_state[type_]
        assert limit is not None

        order = 'received_on'
        if recent_first:
            order = '-{}'.format(order)

        return XFormInstanceSQL.objects.filter(
            domain=domain,
            state=state
        ).order_by(order)[0:limit]

    @staticmethod
    def form_with_id_exists(form_id, domain=None):
        query = XFormInstanceSQL.objects.filter(form_uuid=form_id)
        if domain:
            query = query.filter(domain=domain)
        return query.exists()

    @staticmethod
    def hard_delete_forms(form_ids):
        with transaction.atomic():
            XFormAttachmentSQL.objects.filter(form_id__in=form_ids).delete()
            XFormOperationSQL.objects.filter(form_id__in=form_ids).delete()
            XFormInstanceSQL.objects.filter(form_uuid__in=form_ids).delete()

    @staticmethod
    def archive_form(form_id, user_id=None):
        with transaction.atomic():
            operation = XFormOperationSQL(
                user=user_id,
                operation=XFormOperationSQL.ARCHIVE,
                date=datetime.utcnow(),
                form_id=form_id
            )
            operation.save()
            XFormInstanceSQL.objects.filter(form_uuid=form_id).update(state=XFormInstanceSQL.ARCHIVED)
            CaseTransaction.objects.filter(form_uuid=form_id).update(revoked=True)

    @staticmethod
    def unarchive_form(form_id, user_id=None):
        with transaction.atomic():
            operation = XFormOperationSQL(
                user=user_id,
                operation=XFormOperationSQL.UNARCHIVE,
                date=datetime.utcnow(),
                form_id=form_id
            )
            operation.save()
            XFormInstanceSQL.objects.filter(form_uuid=form_id).update(state=XFormInstanceSQL.NORMAL)
            CaseTransaction.objects.filter(form_uuid=form_id).update(revoked=False)

    @staticmethod
    def get_form_history(form_id):
        return list(XFormOperationSQL.objects.filter(form_id=form_id).order_by('date'))

    @staticmethod
    def get_attachment(form_id, attachment_name):
        return XFormAttachmentSQL.objects.filter(form_id=form_id, name=attachment_name).first()


class CaseAccessorSQL(AbstractCaseAccessor):

    @staticmethod
    def get_case(case_id):
        try:
            return CommCareCaseSQL.objects.get(case_uuid=case_id)
        except CommCareCaseSQL.DoesNotExist:
            raise CaseNotFound

    @staticmethod
    def get_cases(case_ids, ordered=False):
        cases = list(CommCareCaseSQL.objects.filter(case_uuid__in=list(case_ids)).all())
        if ordered:
            # SQL won't return the rows in any particular order so we need to order them ourselves
            index_map = {id_: index for index, id_ in enumerate(case_ids)}
            ordered_cases = [None] * len(case_ids)
            for case in cases:
                ordered_cases[index_map[case.case_id]] = case

            cases = ordered_cases

        return cases

    @staticmethod
    def case_modified_since(case_id, server_modified_on):
        """
        Return True if a case has been modified since the given modification date.
        Assumes that the case exists in the DB.
        """
        return not CommCareCaseSQL.objects.filter(
            case_uuid=case_id,
            server_modified_on=server_modified_on
        ).exists()

    @staticmethod
    def get_case_xform_ids(case_id):
        return list(CaseTransaction.objects.filter(
            case_id=case_id,
            revoked=False,
            form_uuid__isnull=False,
            type=CaseTransaction.TYPE_FORM
        ).values_list('form_uuid', flat=True))

    @staticmethod
    def get_indices(case_id):
        return list(CommCareCaseIndexSQL.objects.filter(case_id=case_id).all())

    @staticmethod
    def get_reverse_indices(case_id):
        return list(CommCareCaseIndexSQL.objects.filter(referenced_id=case_id).all())

    @staticmethod
    def get_reverse_indexed_cases(domain, case_ids):
        return CommCareCaseSQL.objects.filter(
            domain=domain, index__referenced_id__in=case_ids
        ).defer("case_json").prefetch_related('indices')

    @staticmethod
    def hard_delete_case(case_id):
        with transaction.atomic():
            CommCareCaseIndexSQL.objects.filter(case_id=case_id).delete()
            CaseAttachmentSQL.objects.filter(case_id=case_id).delete()
            CaseTransaction.objects.filter(case_id=case_id).delete()
            CommCareCaseSQL.objects.filter(case_uuid=case_id).delete()

    @staticmethod
    def get_attachment(case_id, attachment_name):
        return CaseAttachmentSQL.objects.filter(case_id=case_id, name=attachment_name).first()

    @staticmethod
    def get_attachments(case_id):
        return list(CaseAttachmentSQL.objects.filter(case_id=case_id).all())

    @staticmethod
    def get_transactions_for_case_rebuild(case_id):
        return list(CaseTransaction.objects.filter(
            case_id=case_id,
            revoked=False,
            type__in=CaseTransaction.TYPES_TO_PROCESS
        ).all())

    @staticmethod
    def get_case_by_location(domain, location_id):
        try:
            return CommCareCaseSQL.objects.filter(
                domain=domain,
                type='supply-point',
                location_uuid=location_id
            ).get()
        except CommCareCaseSQL.DoesNotExist:
            return None

    @staticmethod
    def get_case_ids_in_domain(domain, type=None):
        query = CommCareCaseSQL.objects.filter(domain=domain)
        if type:
            query.filter(type=type)
        return list(query.values_list('case_uuid', flat=True))
