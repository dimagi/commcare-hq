from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL

from dimagi.utils.chunked import chunked

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


class CaseAccessorSQL(object):
    @staticmethod
    def get_case_ids_in_domain(domain, type=None):
        query = CommCareCaseSQL.objects.filter(domain=domain)
        if type:
            query.filter(type=type)
        return list(query.values_list('case_uuid', flat=True))

    @staticmethod
    def get_cases_in_domain(domain, type=None):
        case_ids = CaseAccessorSQL.get_case_ids_in_domain(domain, type)
        for ids in chunked(case_ids, 500):
            for case in CaseAccessorSQL.objects.filter(case_uuid__in=ids).iterator():
                yield case
