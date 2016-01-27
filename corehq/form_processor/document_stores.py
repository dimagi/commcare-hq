from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from pillowtop.dao.interface import ReadOnlyDocumentStore


class ReadonlyFormDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.form_accessors = FormAccessors(domain=domain)

    def get_document(self, doc_id):
        return self.form_accessors.get_form(doc_id).to_json()
