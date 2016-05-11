from collections import defaultdict

from corehq.blobs import Error as BlobError
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL, CaseAccessorSQL
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound, LedgerValueNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors, LedgerAccessors
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.form_processor.utils.xform import add_couch_properties_to_sql_form_json
from dimagi.utils.decorators.memoized import memoized
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import ReadOnlyDocumentStore


class ReadonlyFormDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.form_accessors = FormAccessors(domain=domain)

    def get_document(self, doc_id):
        try:
            return add_couch_properties_to_sql_form_json(self.form_accessors.get_form(doc_id).to_json())
        except (XFormNotFound, BlobError) as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self, last_id=None):
        # todo: support last_id
        return iter(self.form_accessors.get_all_form_ids_in_domain())

    def iter_documents(self, ids):
        for wrapped_form in self.form_accessors.iter_forms(ids):
            yield add_couch_properties_to_sql_form_json(wrapped_form.to_json())


class ReadonlyCaseDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.case_accessors = CaseAccessors(domain=domain)

    def get_document(self, doc_id):
        try:
            return self.case_accessors.get_case(doc_id).to_json()
        except CaseNotFound as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self, last_id=None):
        # todo: support last_id
        return iter(self.case_accessors.get_case_ids_in_domain())

    def iter_documents(self, ids):
        for wrapped_case in self.case_accessors.iter_cases(ids):
            yield wrapped_case.to_json()


class ReadonlyLedgerDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        assert should_use_sql_backend(domain), "Only SQL backend supported"
        self.domain = domain
        self.ledger_accessors = LedgerAccessorSQL
        self.case_accessors = CaseAccessorSQL

    def get_document(self, doc_id):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        try:
            ref = UniqueLedgerReference.from_id(doc_id)
            return self.ledger_accessors.get_ledger_value(**ref._asdict()).to_json()
        except LedgerValueNotFound as e:
            raise DocumentNotFoundError(e)

    @property
    @memoized
    def product_ids(self):
        from corehq.apps.products.models import Product
        return Product.ids_by_domain(self.domain)

    def iter_document_ids(self, last_id=None):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        # todo: support last_id
        # assuming we're only interested in the 'stock' section for now
        for case_id in self.case_accessors.get_case_ids_in_domain(self.domain):
            for product_id in self.product_ids:
                yield UniqueLedgerReference(case_id, 'stock', product_id).to_id()

    def iter_documents(self, ids):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        case_id_map = defaultdict(list)
        for id_string in ids:
            case_id, section_id, entry_id = UniqueLedgerReference.from_id(id_string)
            case_id_map[(section_id, entry_id)].append(case_id)
        for section_entry, case_ids in case_id_map.iteritems():
            section_id, entry_id = section_entry
            results = self.ledger_accessors.get_ledger_values_for_cases(case_ids, section_id, entry_id)
            for ledger_value in results:
                yield ledger_value
