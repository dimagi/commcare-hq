from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit.exceptions import ResourceNotFound
from datetime import datetime

from casexml.apps.case.dbaccessors import (
    get_extension_case_ids,
    get_indexed_case_ids,
    get_all_reverse_indices_info,
    get_open_case_ids_in_domain,
    get_reverse_indexed_cases,
    get_related_indices,
)
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import get_case_xform_ids, iter_cases
from casexml.apps.stock.models import StockTransaction
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.apps.commtrack.models import StockState
from corehq.apps.hqcase.dbaccessors import (
    get_case_ids_in_domain,
    get_open_case_ids,
    get_closed_case_ids,
    get_case_ids_in_domain_by_owner,
    get_cases_in_domain_by_external_id,
    get_deleted_case_ids_by_owner,
    get_all_case_owner_ids)
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
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
    get_forms_by_id,
    get_form_ids_by_type,
    iter_form_ids_by_xmlns,
)
from couchforms.models import XFormInstance, doc_types, XFormOperation
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.parsing import json_format_datetime
import six


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
        doc = XFormInstance.get_db().get(form_id)
        doc = doc_types()[doc['doc_type']].wrap(doc)
        if doc.external_blobs:
            for name, meta in six.iteritems(doc.external_blobs):
                with doc.fetch_attachment(name, stream=True) as content:
                    doc.deferred_put_attachment(
                        content,
                        name,
                        content_type=meta.content_type,
                        content_length=meta.content_length,
                    )
        else:
            # xforms are expected to at least have the XML attachment
            raise ResourceNotFound("XForm attachment missing: {}".format(form_id))
        return doc

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
    def soft_delete_forms(domain, form_ids, deletion_date=None, deletion_id=None):
        def _form_delete(doc):
            doc['server_modified_on'] = json_format_datetime(datetime.utcnow())
        return _soft_delete(XFormInstance.get_db(), form_ids, deletion_date, deletion_id, _form_delete)

    @staticmethod
    def soft_undelete_forms(domain, form_ids):
        def _form_undelete(doc):
            doc['server_modified_on'] = json_format_datetime(datetime.utcnow())
        return _soft_undelete(XFormInstance.get_db(), form_ids, _form_undelete)

    @staticmethod
    def modify_attachment_xml_and_metadata(form_data, form_attachment_new_xml, new_username):
        # Update XML
        form_data.put_attachment(form_attachment_new_xml, name="form.xml", content_type='text/xml')
        operation = XFormOperation(user_id=SYSTEM_USER_ID, date=datetime.utcnow(),
                                   operation='gdpr_scrub')
        form_data.history.append(operation)
        # Update metadata
        form_data.form['meta']['username'] = new_username
        form_data.save()

    @staticmethod
    def iter_form_ids_by_xmlns(domain, xmlns=None):
        return iter_form_ids_by_xmlns(domain, xmlns)


class CaseAccessorCouch(AbstractCaseAccessor):

    @staticmethod
    def get_case(case_id):
        return CommCareCase.get(case_id)

    @staticmethod
    def get_cases(case_ids, ordered=False, prefetched_indices=None):
        # prefetched_indices is ignored sinces cases already have them
        return [
            CommCareCase.wrap(doc) for doc in iter_docs(
                CommCareCase.get_db(),
                case_ids
            )
        ]

    @staticmethod
    def get_related_indices(domain, case_ids, exclude_indices):
        return get_related_indices(domain, case_ids, exclude_indices)

    @staticmethod
    def get_closed_and_deleted_ids(domain, case_ids):
        """Get the subset of given list of case ids that are closed or deleted

        WARNING this is inefficient (better version in SQL).
        """
        return [(case.case_id, case.closed, case.is_deleted)
            for case in iter_cases(case_ids)
            if case.domain == domain and (case.closed or case.is_deleted)]

    @staticmethod
    def get_modified_case_ids(accessor, case_ids, sync_log):
        """Get the subset of given list of case ids that have been modified
        since sync date/log id

        WARNING this is inefficient (better version in SQL).
        """
        return [case.case_id
            for case in accessor.iter_cases(case_ids)
            if not case.is_deleted and case.modified_since_sync(sync_log)]

    @staticmethod
    def case_exists(case_id):
        return CommCareCase.get_db().doc_exist(case_id)

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
    def get_extension_case_ids(domain, case_ids, include_closed=True):
        # include_closed ignored for couch
        return get_extension_case_ids(domain, case_ids)

    @staticmethod
    def get_indexed_case_ids(domain, case_ids):
        return get_indexed_case_ids(domain, case_ids)

    @staticmethod
    def get_reverse_indexed_cases(domain, case_ids, case_types=None, is_closed=None):
        return [case for case in get_reverse_indexed_cases(domain, case_ids)
                if (not case_types or case.type in case_types)
                and (is_closed is None or case.closed == is_closed)]

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
    def get_cases_by_external_id(domain, external_id, case_type=None):
        cases = get_cases_in_domain_by_external_id(domain, external_id)
        if case_type:
            return [case for case in cases if case.type == case_type]
        return cases

    @staticmethod
    def soft_delete_cases(domain, case_ids, deletion_date=None, deletion_id=None):
        return _soft_delete(CommCareCase.get_db(), case_ids, deletion_date, deletion_id)

    @staticmethod
    def soft_undelete_cases(domain, case_ids):
        return _soft_undelete(CommCareCase.get_db(), case_ids)

    @staticmethod
    def get_deleted_case_ids_by_owner(domain, owner_id):
        return get_deleted_case_ids_by_owner(owner_id)

    @staticmethod
    def get_case_owner_ids(domain):
        return get_all_case_owner_ids(domain)


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

    @staticmethod
    def get_ledger_values_for_cases(case_ids, section_id=None, entry_id=None, date_start=None, date_end=None):
        from corehq.apps.commtrack.models import StockState

        assert isinstance(case_ids, list)
        if not case_ids:
            return []

        filters = {'case_id__in': case_ids}
        if section_id:
            filters['section_id'] = section_id
        if entry_id:
            filters['product_id'] = entry_id
        if date_start:
            filters['last_modifed__gte'] = date_start
        if date_end:
            filters['last_modified__lte'] = date_end

        return list(StockState.objects.filter(**filters))


def _get_attachment_content(doc_class, doc_id, attachment_id):
    try:
        doc = doc_class.get(doc_id)
        resp = doc.fetch_attachment(attachment_id, stream=True)
        content_type = doc.blobs[attachment_id].content_type
    except ResourceNotFound:
        raise AttachmentNotFound(attachment_id)

    return AttachmentContent(content_type, resp)


def _soft_delete(db, doc_ids, deletion_date=None, deletion_id=None, custom_delete=None):
    from dimagi.utils.couch.undo import DELETED_SUFFIX
    deletion_date = json_format_datetime(deletion_date or datetime.utcnow())

    def delete(doc):
        doc['doc_type'] += DELETED_SUFFIX
        doc['-deletion_id'] = deletion_id
        doc['-deletion_date'] = deletion_date

        if custom_delete:
            custom_delete(doc)

        return doc

    return _operate_on_docs(db, doc_ids, delete)


def _soft_undelete(db, doc_ids, custom_undelete=None):
    from dimagi.utils.couch.undo import DELETED_SUFFIX

    def undelete(doc):

        doc_type = doc['doc_type']
        if doc_type.endswith(DELETED_SUFFIX):
            doc['doc_type'] = doc_type[:-len(DELETED_SUFFIX)]

        if '-deletion_id' in doc:
            del doc['-deletion_id']
        if '-deletion_date' in doc:
            del doc['-deletion_date']

        if custom_undelete:
            custom_undelete(doc)
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
