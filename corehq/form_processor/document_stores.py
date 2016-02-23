from corehq.blobs import Error as BlobError
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import ReadOnlyDocumentStore


class ReadonlyFormDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.form_accessors = FormAccessors(domain=domain)

    def get_document(self, doc_id):
        try:
            return self.form_accessors.get_form(doc_id).to_json()
        except (XFormNotFound, BlobError) as e:
            raise DocumentNotFoundError(e)


class ReadonlyCaseDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.case_accessors = CaseAccessors(domain=domain)

    def get_document(self, doc_id):
        try:
            return self.case_accessors.get_case(doc_id).to_json()
        except CaseNotFound as e:
            raise DocumentNotFoundError(e)
