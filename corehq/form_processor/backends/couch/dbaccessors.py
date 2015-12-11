from casexml.apps.case.dbaccessors import get_extension_case_ids, \
    get_indexed_case_ids
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import get_case_xform_ids
from corehq.apps.hqcase.dbaccessors import (
    get_open_case_ids,
    get_closed_case_ids)
from corehq.form_processor.interfaces.dbaccessors import AbstractCaseAccessor, AbstractFormAccessor
from couchforms.dbaccessors import get_forms_by_type
from couchforms.models import XFormInstance, doc_types
from dimagi.utils.couch.database import iter_docs


class FormAccessorCouch(AbstractFormAccessor):
    @staticmethod
    def get_form(form_id):
        return XFormInstance.get(form_id)

    @staticmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        return get_forms_by_type(domain, type_, recent_first, limit)

    @staticmethod
    def get_with_attachments(form_id):
        doc = XFormInstance.get_db().get(form_id, attachments=True)
        return doc_types()[doc['doc_type']].wrap(doc)

    @staticmethod
    def save_new_form(form):
        form.save()

    @staticmethod
    def update_form_problem_and_state(form):
        form.save()


class CaseAccessorCouch(AbstractCaseAccessor):

    @staticmethod
    def get_case(case_id):
        return CommCareCase.get(case_id)

    @staticmethod
    def get_cases(case_ids, ordered=False):
        return [
            CommCareCase.wrap(doc) for doc in iter_docs(
                CommCareCase.get_db(),
                case_ids
            )
        ]

    @staticmethod
    def get_case_xform_ids(case_id):
        return get_case_xform_ids(case_id)

    @staticmethod
    def get_case_ids_in_domain(domain, type=None):
        return get_case_ids_in_domain(domain, type=type)

    @staticmethod
    def get_open_case_ids(domain, owner_id):
        return get_open_case_ids(domain, owner_id)

    @staticmethod
    def get_closed_case_ids(domain, owner_id):
        return get_closed_case_ids(domain, owner_id)

    @staticmethod
    def get_extension_case_ids(domain, case_ids):
        return get_extension_case_ids(domain, case_ids)

    @staticmethod
    def get_indexed_case_ids(domain, case_ids):
        return get_indexed_case_ids(domain, case_ids)
