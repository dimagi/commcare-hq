from collections import defaultdict

from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import DocumentStore

from corehq.blobs import Error as BlobError
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseReindexAccessor,
    LedgerAccessorSQL,
    LedgerReindexAccessor,
    iter_all_ids,
)
from corehq.form_processor.exceptions import (
    CaseNotFound,
    LedgerValueNotFound,
    MissingFormXml,
    XFormNotFound,
)
from corehq.form_processor.models import CommCareCase, XFormInstance


class UnexpectedBackend(Exception):
    pass


class FormDocumentStore(DocumentStore):

    def __init__(self, domain, xmlns=None):
        self.domain = domain
        self.xmlns = xmlns

    def get_document(self, doc_id):
        try:
            form = XFormInstance.objects.get_form(doc_id, self.domain)
            return self._to_json(form)
        except (XFormNotFound, BlobError) as e:
            raise DocumentNotFoundError(e)

    @staticmethod
    def _to_json(form):
        if isinstance(form, XFormInstance):
            return form.to_json(include_attachments=True)
        else:
            return form.to_json()

    def iter_document_ids(self):
        return iter(XFormInstance.objects.iter_form_ids_by_xmlns(self.domain, self.xmlns))

    def iter_documents(self, ids):
        for wrapped_form in XFormInstance.objects.iter_forms(ids, self.domain):
            try:
                yield self._to_json(wrapped_form)
            except (DocumentNotFoundError, MissingFormXml):
                pass


class CaseDocumentStore(DocumentStore):

    def __init__(self, domain, case_type=None):
        self.domain = domain
        self.case_type = case_type

    def get_document(self, doc_id, *, external_id=None):
        try:
            if external_id is None:
                return CommCareCase.objects.get_case(doc_id, self.domain).to_json()
            else:
                case = CommCareCase.objects.get_case_by_external_id(
                    self.domain,
                    external_id,
                    raise_multiple=True
                )
                if case:
                    return case.to_json()
                raise CaseNotFound(f"external_id: '{external_id}'")
        except (CaseNotFound, CommCareCase.MultipleObjectsReturned) as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self):
        accessor = CaseReindexAccessor(self.domain, case_type=self.case_type)
        return iter_all_ids(accessor)

    def iter_documents(self, ids):
        for wrapped_case in CommCareCase.objects.iter_cases(ids, self.domain):
            yield wrapped_case.to_json()


class LedgerV2DocumentStore(DocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.ledger_accessors = LedgerAccessorSQL

    def get_document(self, doc_id):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        try:
            ref = UniqueLedgerReference.from_id(doc_id)
            return self.ledger_accessors.get_ledger_value(**ref._asdict()).to_json()
        except LedgerValueNotFound as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self):
        accessor = LedgerReindexAccessor(self.domain)
        return iter_all_ids(accessor)

    def iter_documents(self, ids):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        case_id_map = defaultdict(list)
        for id_string in ids:
            case_id, section_id, entry_id = UniqueLedgerReference.from_id(id_string)
            case_id_map[(section_id, entry_id)].append(case_id)
        for section_entry, case_ids in case_id_map.items():
            section_id, entry_id = section_entry
            results = self.ledger_accessors.get_ledger_values_for_cases(case_ids, [section_id], [entry_id])
            for ledger_value in results:
                yield ledger_value.to_json()


class DocStoreLoadTracker(object):

    def __init__(self, store, track_load):
        self.store = store
        self.track_load = track_load

    def get_document(self, doc_id, *args, **kwargs):
        self.track_load()
        return self.store.get_document(doc_id, *args, **kwargs)

    def iter_documents(self, ids):
        for doc in self.store.iter_documents(ids):
            self.track_load()
            yield doc

    def __getattr__(self, name):
        return getattr(self.store, name)

    def __repr__(self):
        return 'DocStoreLoadTracker({})'.format(repr(self.store))
