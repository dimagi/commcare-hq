from corehq.doctypemigrations.bulk_migrate import get_all_docs_with_doc_types


def delete_all_docs_by_doc_type(db, doc_types):
    db.bulk_delete(get_all_docs_with_doc_types(db, doc_types))
