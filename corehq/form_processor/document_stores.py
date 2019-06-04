from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

from corehq.blobs import Error as BlobError
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL, CaseAccessorSQL, \
    iter_all_ids, CaseReindexAccessor
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound, LedgerValueNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.util.quickcache import quickcache
from pillowtop.dao.django import DjangoDocumentStore
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import ReadOnlyDocumentStore
import six


class ReadonlyFormDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain, xmlns=None):
        self.domain = domain
        self.form_accessors = FormAccessors(domain=domain)
        self.xmlns = xmlns

    def get_document(self, doc_id):
        try:
            form = self.form_accessors.get_form(doc_id)
            if isinstance(form, XFormInstanceSQL):
                return form.to_json(include_attachments=True)
            else:
                return form.to_json()
        except (XFormNotFound, BlobError) as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self, last_id=None):
        # todo: support last_id
        return iter(self.form_accessors.iter_form_ids_by_xmlns(self.xmlns))

    def iter_documents(self, ids):
        for wrapped_form in self.form_accessors.iter_forms(ids):
            yield wrapped_form.to_json()


class ReadonlyCaseDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain, case_type=None):
        self.domain = domain
        self.case_accessors = CaseAccessors(domain=domain)
        self.case_type = case_type

    def get_document(self, doc_id):
        try:
            return self.case_accessors.get_case(doc_id).to_json()
        except CaseNotFound as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self, last_id=None):
        accessor = CaseReindexAccessor(self.domain, case_type=self.case_type)
        return iter(iter_all_ids(accessor))

    def iter_documents(self, ids):
        for wrapped_case in self.case_accessors.iter_cases(ids):
            yield wrapped_case.to_json()


class ReadonlyLedgerV2DocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        assert should_use_sql_backend(domain), "Only SQL backend supported: {}".format(domain)
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
    @quickcache(['self.domain'], timeout=30 * 60)
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
        for section_entry, case_ids in six.iteritems(case_id_map):
            section_id, entry_id = section_entry
            results = self.ledger_accessors.get_ledger_values_for_cases(case_ids, section_id, entry_id)
            for ledger_value in results:
                yield ledger_value.to_json()


class LedgerV1DocumentStore(DjangoDocumentStore):

    def __init__(self, domain):
        from corehq.apps.commtrack.models import StockState
        assert not should_use_sql_backend(domain), "Only non-SQL backend supported"
        self.domain = domain

        def _doc_gen_fn(obj):
            return obj.to_json()

        super(LedgerV1DocumentStore, self).__init__(
            StockState, _doc_gen_fn, model_manager=StockState.include_archived)


class DocStoreLoadTracker(object):

    def __init__(self, store, track_load):
        self.store = store
        self.track_load = track_load

    def get_document(self, doc_id):
        self.track_load()
        return self.store.get_document(doc_id)

    def iter_documents(self, ids):
        for doc in self.store.iter_documents(ids):
            self.track_load()
            yield doc

    def __getattr__(self, name):
        return getattr(self.store, name)
