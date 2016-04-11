from corehq.blobs import Error as BlobError
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.utils.xform import add_couch_properties_to_sql_form_json
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
