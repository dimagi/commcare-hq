from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

from corehq.blobs import Error as BlobError
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL, \
    iter_all_ids, CaseReindexAccessor, LedgerReindexAccessor
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
        if should_use_sql_backend(self.domain):
            accessor = CaseReindexAccessor(self.domain, case_type=self.case_type)
            return iter_all_ids(accessor)
        else:
            return iter(self.case_accessors.get_case_ids_in_domain(self.case_type))

    def iter_documents(self, ids):
        for wrapped_case in self.case_accessors.iter_cases(ids):
            yield wrapped_case.to_json()


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

    def __repr__(self):
        return 'DocStoreLoadTracker({})'.format(repr(self.store))
