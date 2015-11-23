from django.db import transaction
from django.db.models import Prefetch

from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseIndexSQL, CaseAttachmentSQL, CaseTransaction, \
    CommCareCaseSQL, XFormAttachmentSQL, XFormOperationSQL

doc_type_to_state = {
    "XFormInstance": XFormInstanceSQL.NORMAL,
    "XFormError": XFormInstanceSQL.ERROR,
    "XFormDuplicate": XFormInstanceSQL.DUPLICATE,
    "XFormDeprecated": XFormInstanceSQL.DEPRECATED,
    "XFormArchived": XFormInstanceSQL.ARCHIVED,
    "SubmissionErrorLog": XFormInstanceSQL.SUBMISSION_ERROR_LOG
}


class FormAccessorSQL(object):

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
    def get_forms_with_attachments(form_ids):
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
            XFormAttachmentSQL.objects.filter(xform_id__in=form_ids).delete()
            XFormOperationSQL.objects.filter(xform_id__in=form_ids).delete()
            XFormInstanceSQL.objects.filter(form_uuid__in=form_ids).delete()


class CaseDbAccessor(object):
    @staticmethod
    def hard_delete_case(case_id):
        with transaction.atomic():
            CommCareCaseIndexSQL.objects.filter(case_id=case_id).delete()
            CaseAttachmentSQL.objects.filter(case_id=case_id).delete()
            CaseTransaction.objects.filter(case_id=case_id).delete()
            CommCareCaseSQL.objects.filter(case_uuid=case_id).delete()
