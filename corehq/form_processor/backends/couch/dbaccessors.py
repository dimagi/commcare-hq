from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import get_case_xform_ids
from corehq.form_processor.interfaces.dbaccessors import AbstractCaseAccessor
from couchforms.dbaccessors import get_forms_by_type
from dimagi.utils.couch.database import iter_docs


class FormAccessorCouch(object):

    @staticmethod
    def get_forms_by_type(domain, type_, recent_first=False, limit=None):
        return get_forms_by_type(domain, type_, recent_first, limit)


class CaseAccessorCouch(AbstractCaseAccessor):

    @staticmethod
    def get_case(case_id):
        return CommCareCase.get(case_id)

    @staticmethod
    def get_cases(case_ids):
        return [
            CommCareCase.wrap(doc) for doc in iter_docs(
                CommCareCase.get_db(),
                case_ids
            )
        ]

    @staticmethod
    def get_case_xform_ids(case_id):
        return get_case_xform_ids(case_id)
