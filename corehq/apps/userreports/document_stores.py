from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.document_stores import ReadonlyFormDocumentStore, ReadonlyCaseDocumentStore
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.couch import get_db_by_doc_type
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import ReadOnlyDocumentStore


class ReadonlyLocationDocumentStore(ReadOnlyDocumentStore):

    def __init__(self, domain):
        self.domain = domain
        self.queryset = SQLLocation.objects.filter(domain=domain)

    def get_document(self, doc_id):
        try:
            return self.queryset.get(location_id=doc_id).to_json()
        except SQLLocation.DoesNotExist as e:
            raise DocumentNotFoundError(e)

    def iter_document_ids(self, last_id=None):
        return iter(self.queryset.location_ids())

    def iter_documents(self, ids):
        for location in self.queryset.filter(location_id__in=ids):
            yield location.to_json()


def get_document_store(domain, doc_type):
    use_sql = should_use_sql_backend(domain)
    if use_sql and doc_type == 'XFormInstance':
        return ReadonlyFormDocumentStore(domain)
    elif use_sql and doc_type == 'CommCareCase':
        return ReadonlyCaseDocumentStore(domain)
    elif doc_type == 'Location':
        return ReadonlyLocationDocumentStore(domain)
    else:
        # all other types still live in couchdb
        return CouchDocumentStore(
            couch_db=get_db_by_doc_type(doc_type),
            domain=domain,
            doc_type=doc_type
        )
