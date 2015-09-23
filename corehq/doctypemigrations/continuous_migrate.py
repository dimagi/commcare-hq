from dimagi.utils.chunked import chunked


def filter_doc_ids_by_doc_type(db, doc_ids, doc_types):
    for doc_ids_chunk in chunked(doc_ids, 100):
        keys = [[doc_type, doc_id]
                for doc_id in doc_ids_chunk
                for doc_type in doc_types]
        results = db.view('all_docs/by_doc_type', keys=keys)
        for result in results:
            yield result['id']
