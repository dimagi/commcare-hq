from couchdbkit import ResourceNotFound

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.dbaccessors import get_reverse_indices_for_case_id
from casexml.apps.case.util import get_case_xform_ids
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain

from ..utils import to_generic
from ..exceptions import CaseNotFound


class CaseInterface(object):

    @classmethod
    def get_attachment(cls, case_id, attachment_name):
        case = cls._get_case(case_id)
        return case.get_attachment(attachment_name)

    @classmethod
    @to_generic
    def get_case(cls, case_id):
        try:
            return cls._get_case(case_id)
        except ResourceNotFound:
            raise CaseNotFound

    @classmethod
    def to_xml(cls, case_id, version):
        case = cls._get_case(case_id)
        return case.to_xml(version)

    @staticmethod
    def _get_case(case_id):
        return CommCareCase.get(case_id)

    @staticmethod
    @to_generic
    def get_cases(case_ids):
        return [
            CommCareCase.wrap(doc) for doc in iter_docs(
                CommCareCase.get_db(),
                case_ids
            )
        ]

    @staticmethod
    def get_cases_in_domain(domain):
        case_ids = CaseInterface.get_case_ids_in_domain(domain)
        return CaseInterface.get_cases(case_ids)

    @staticmethod
    def get_case_ids_in_domain(domain):
        return get_case_ids_in_domain(domain)

    @staticmethod
    def get_reverse_indices(domain, case_id):
        return get_reverse_indices_for_case_id(domain, case_id)

    @staticmethod
    def get_case_xform_ids_from_couch(case_id):
        return get_case_xform_ids(case_id)

    @classmethod
    @to_generic
    def soft_delete(cls, case_id):
        case = cls._get_case(case_id)
        case.doc_type += DELETED_SUFFIX
        case.save()
        return case

    @classmethod
    def hard_delete(cls, case_generic):
        from casexml.apps.case.cleanup import safe_hard_delete
        case = cls._get_case(case_generic.id)
        safe_hard_delete(case)
