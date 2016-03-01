from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.dbaccessors import get_extension_case_ids, \
    get_indexed_case_ids, get_all_reverse_indices_info
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import get_case_xform_ids
from corehq.apps.hqcase.dbaccessors import (
    get_case_ids_in_domain,
    get_open_case_ids,
    get_closed_case_ids,
    get_case_ids_in_domain_by_owner,
    get_case_types_for_domain)
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.dbaccessors.couchapps.cases_by_server_date.by_owner_server_modified_on import \
    get_case_ids_modified_with_owner_since
from corehq.dbaccessors.couchapps.cases_by_server_date.by_server_modified_on import \
    get_last_modified_dates
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import (
    AbstractCaseAccessor, AbstractFormAccessor, AttachmentContent
)
from couchforms.dbaccessors import (
    get_forms_by_type,
    get_deleted_form_ids_for_user,
    get_form_ids_for_user,
    get_forms_by_id)
from couchforms.models import XFormInstance, doc_types
from dimagi.utils.couch.database import iter_docs


class FormAccessorCouch(AbstractFormAccessor):
    @staticmethod
    def form_exists(self, form_id, domain=None):
        if not domain:
            return XFormInstance.get_db().doc_exist(form_id)
        else:
            try:
                xform = XFormInstance.get(form_id)
            except ResourceNotFound:
                return False

            return xform.domain == domain

    @staticmethod
    def get_form(form_id):
        return XFormInstance.get(form_id)

    @staticmethod
    def get_forms(form_ids):
        return get_forms_by_id(form_ids)

    @staticmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        return get_forms_by_type(domain, type_, recent_first, limit)

    @staticmethod
    def get_with_attachments(form_id):
        doc = XFormInstance.get_db().get(form_id, attachments=True)
        return doc_types()[doc['doc_type']].wrap(doc)

    @staticmethod
    def get_attachment_content(form_id, attachment_id):
        return _get_attachment_content(XFormInstance, form_id, attachment_id)

    @staticmethod
    def save_new_form(form):
        form.save()

    @staticmethod
    def update_form_problem_and_state(form):
        form.save()

    @staticmethod
    def get_deleted_forms_for_user(domain, user_id, ids_only=False):
        doc_ids = get_deleted_form_ids_for_user(user_id)
        if ids_only:
            return doc_ids
        return [XFormInstance.wrap(doc) for doc in iter_docs(XFormInstance.get_db(), doc_ids)]

    @staticmethod
    def get_forms_for_user(domain, user_id, ids_only=False):
        doc_ids = get_form_ids_for_user(domain, user_id)
        if ids_only:
            return doc_ids
        return [XFormInstance.wrap(doc) for doc in iter_docs(XFormInstance.get_db(), doc_ids)]


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
    def get_case_ids_in_domain_by_owners(domain, owner_ids):
        return get_case_ids_in_domain_by_owner(domain, owner_id__in=owner_ids)

    @staticmethod
    def get_open_case_ids(domain, owner_id):
        return get_open_case_ids(domain, owner_id)

    @staticmethod
    def get_closed_case_ids(domain, owner_id):
        return get_closed_case_ids(domain, owner_id)

    @staticmethod
    def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date):
        return get_case_ids_modified_with_owner_since(domain, owner_id, reference_date)

    @staticmethod
    def get_extension_case_ids(domain, case_ids):
        return get_extension_case_ids(domain, case_ids)

    @staticmethod
    def get_indexed_case_ids(domain, case_ids):
        return get_indexed_case_ids(domain, case_ids)

    @staticmethod
    def get_last_modified_dates(domain, case_ids):
        return get_last_modified_dates(domain, case_ids)

    @staticmethod
    def get_all_reverse_indices_info(domain, case_ids):
        return get_all_reverse_indices_info(domain, case_ids)

    @staticmethod
    def get_attachment_content(case_id, attachment_id):
        return _get_attachment_content(CommCareCase, case_id, attachment_id)

    @staticmethod
    def get_case_by_domain_hq_user_id(domain, user_id, case_type):
        return get_case_by_domain_hq_user_id(domain, user_id, case_type)

    @staticmethod
    def get_case_types_for_domain(domain):
        return get_case_types_for_domain(domain)


def _get_attachment_content(doc_class, doc_id, attachment_id):
    try:
        resp = doc_class.get_db().fetch_attachment(doc_id, attachment_id, stream=True)
    except ResourceNotFound:
        raise AttachmentNotFound(attachment_id)

    headers = resp.resp.headers
    content_type = headers.get('Content-Type', None)
    return AttachmentContent(content_type, resp)
