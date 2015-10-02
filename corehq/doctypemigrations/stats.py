from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type


def get_doc_counts_per_doc_type(db, doc_types):
    return {doc_type: get_doc_count_by_type(db, doc_type) for doc_type in doc_types}
