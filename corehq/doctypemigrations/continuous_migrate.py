from corehq.util.couch import IterDB
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.chunked import chunked


def filter_doc_ids_by_doc_type(db, doc_ids, doc_types):
    for doc_ids_chunk in chunked(doc_ids, 100):
        keys = [[doc_type, doc_id]
                for doc_id in doc_ids_chunk
                for doc_type in doc_types]
        results = db.view('all_docs/by_doc_type', keys=keys)
        for result in results:
            yield result['id']


def copy_docs(source_db, target_db, doc_ids):
    """
    copy docs from source_db to target_db
    by doc_id

    """
    with IterDB(target_db, new_edits=False) as iter_db:
        for doc in iter_docs(source_db, doc_ids, attachments=True):
            iter_db.save(doc)


def delete_docs(target_db, doc_id_rev_pairs):
    """
    delete docs from database by doc _id and _rev
    """
    with IterDB(target_db, new_edits=False) as iter_db:
        for doc_id, doc_rev in doc_id_rev_pairs:
            iter_db.delete({'_id': doc_id, '_rev': doc_rev})
