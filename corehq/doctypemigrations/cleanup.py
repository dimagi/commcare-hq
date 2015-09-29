from dimagi.utils.chunked import chunked
from corehq.doctypemigrations.bulk_migrate import get_all_docs_with_doc_types


def delete_all_docs_by_doc_type(db, doc_types):
    for chunk in chunked(get_all_docs_with_doc_types(db, doc_types), 100):
        db.bulk_delete(chunk)
