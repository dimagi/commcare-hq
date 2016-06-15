from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime

from casexml.apps.case.dbaccessors import get_extension_case_ids, \
    get_indexed_case_ids, get_all_reverse_indices_info, get_open_case_ids_in_domain, \
    get_reverse_indexed_case_ids
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import get_case_xform_ids
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.hqcase.dbaccessors import (
    get_case_ids_in_domain,
    get_open_case_ids,
    get_closed_case_ids,
    get_case_ids_in_domain_by_owner,
    get_case_types_for_domain,
    get_cases_in_domain_by_external_id,
)
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.blobs.mixin import BlobMixin
from corehq.couchapps.dbaccessors import forms_have_multimedia
from corehq.dbaccessors.couchapps.cases_by_server_date.by_owner_server_modified_on import \
    get_case_ids_modified_with_owner_since
from corehq.dbaccessors.couchapps.cases_by_server_date.by_server_modified_on import \
    get_last_modified_dates
from corehq.form_processor.exceptions import AttachmentNotFound, LedgerValueNotFound
from corehq.form_processor.interfaces.dbaccessors import (
    AbstractCaseAccessor, AbstractFormAccessor, AttachmentContent,
    AbstractLedgerAccessor)
from couchforms.dbaccessors import (
    get_forms_by_type,
    get_deleted_form_ids_for_user,
    get_form_ids_for_user,
    get_forms_by_id, get_form_ids_by_type)
from couchforms.models import XFormInstance, doc_types
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.parsing import json_format_datetime


class FormAccessorCouch(AbstractFormAccessor):

    @staticmethod
    def form_exists(form_id, domain=None):
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
    def get_forms(form_ids, ordered=False):
        return get_forms_by_id(form_ids)

    @staticmethod
    def get_form_ids_in_domain_by_type(domain, type_):
        return get_form_ids_by_type(domain, type_)

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
    def get_deleted_form_ids_for_user(domain, user_id):
        return get_deleted_form_ids_for_user(user_id)

    @staticmethod
    def get_form_ids_for_user(domain, user_id):
        return get_form_ids_for_user(domain, user_id)

    @staticmethod
    def forms_have_multimedia(domain, app_id, xmlns):
        return forms_have_multimedia(domain, app_id, xmlns)

    @staticmethod
    def soft_delete_forms(domain, form_ids, deletion_date=None, deletion_id=None):
        return _soft_delete(XFormInstance.get_db(), form_ids, deletion_date, deletion_id)


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
    def get_case_ids_in_domain_by_owners(domain, owner_ids, closed=None):
        return get_case_ids_in_domain_by_owner(domain, owner_id__in=owner_ids, closed=closed)

    @staticmethod
    def get_open_case_ids_for_owner(domain, owner_id):
        return get_open_case_ids(domain, owner_id)

    @staticmethod
    def get_closed_case_ids_for_owner(domain, owner_id):
        return get_closed_case_ids(domain, owner_id)

    @staticmethod
    def get_open_case_ids_in_domain_by_type(domain, case_type, owner_ids=None):
        owner_ids = owner_ids if owner_ids else [None]
        return [
            case_id
            for owner_id in owner_ids
            for case_id in get_open_case_ids_in_domain(domain, type=case_type, owner_id=owner_id)
        ]

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
    def get_reverse_indexed_cases(domain, case_ids):
        return get_reverse_indexed_case_ids(domain, case_ids)

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

    @staticmethod
    def get_cases_by_external_id(domain, external_id, case_type=None):
        cases = get_cases_in_domain_by_external_id(domain, external_id)
        if case_type:
            return [case for case in cases if case.type == case_type]
        return cases

    @staticmethod
    def soft_delete_cases(domain, case_ids, deletion_date=None, deletion_id=None):
        return _soft_delete(CommCareCase.get_db(), case_ids, deletion_date, deletion_id)


class LedgerAccessorCouch(AbstractLedgerAccessor):

    @staticmethod
    def get_transactions_for_consumption(domain, case_id, product_id, section_id, window_start, window_end):
        from casexml.apps.stock.models import StockTransaction
        db_transactions = StockTransaction.objects.filter(
            case_id=case_id, product_id=product_id,
            report__date__gt=window_start,
            report__date__lte=window_end,
            section_id=section_id,
        ).order_by('report__date', 'pk')

        first = True
        for db_tx in db_transactions:
            # for the very first transaction, include the previous one if there as well
            # to capture the data on the edge of the window
            if first:
                previous = db_tx.get_previous_transaction()
                if previous:
                    yield previous
                first = False

            yield db_tx

    @staticmethod
    def get_ledger_value(case_id, section_id, entry_id):
        try:
            return StockState.objects.get(case_id=case_id, section_id=section_id, product_id=entry_id)
        except StockState.DoesNotExist:
            raise LedgerValueNotFound

    @staticmethod
    def get_ledger_transactions_for_case(case_id, section_id=None, entry_id=None):
        query = StockTransaction.objects.filter(case_id=case_id)
        if entry_id:
            query = query.filter(product_id=entry_id)

        if section_id:
            query.filter(section_id=section_id)

        return query.order_by('report__date', 'pk')

    @staticmethod
    def get_latest_transaction(case_id, section_id, entry_id):
        return StockTransaction.latest(case_id, section_id, entry_id)

    @staticmethod
    def get_ledger_values_for_case(case_id):
        from corehq.apps.commtrack.models import StockState

        return StockState.objects.filter(case_id=case_id)

    @staticmethod
    def get_current_ledger_state(case_ids, ensure_form_id=False):
        from casexml.apps.stock.utils import get_current_ledger_state
        return get_current_ledger_state(case_ids, ensure_form_id=ensure_form_id)


def _get_attachment_content(doc_class, doc_id, attachment_id):
    try:
        if issubclass(doc_class, BlobMixin):
            resp = doc_class.get(doc_id).fetch_attachment(attachment_id, stream=True)
        else:
            resp = doc_class.get_db().fetch_attachment(doc_id, attachment_id, stream=True)
    except ResourceNotFound:
        raise AttachmentNotFound(attachment_id)

    headers = resp.resp.headers
    content_type = headers.get('Content-Type', None)
    return AttachmentContent(content_type, resp)


def _soft_delete(db, doc_ids, deletion_date=None, deletion_id=None):
    from dimagi.utils.couch.undo import DELETED_SUFFIX
    deletion_date = json_format_datetime(deletion_date or datetime.utcnow())

    def delete(doc):
        doc['doc_type'] += DELETED_SUFFIX
        doc['-deletion_id'] = deletion_id
        doc['-deletion_date'] = deletion_date
        return doc

    return _operate_on_docs(db, doc_ids, delete)


def _soft_undelete(db, doc_ids):
    from dimagi.utils.couch.undo import DELETED_SUFFIX

    def undelete(doc):
        doc_type = doc['doc_type']
        if doc_type.endswith(DELETED_SUFFIX):
            doc['doc_type'] = doc_type[:-len(DELETED_SUFFIX)]

        del doc['-deletion_id']
        del doc['-deletion_date']
        return doc

    return _operate_on_docs(db, doc_ids, undelete)


def _operate_on_docs(db, doc_ids, operation_fn):
    docs_to_save = []
    for doc in iter_docs(db, doc_ids):
        doc = operation_fn(doc)
        docs_to_save.append(doc)

        if len(docs_to_save) % 1000 == 0:
            db.bulk_save(docs_to_save)
            docs_to_save = []

    if docs_to_save:
        db.bulk_save(docs_to_save)

    return len(doc_ids)
