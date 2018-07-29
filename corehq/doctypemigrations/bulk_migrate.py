from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.util.couch import IterDB


def _insert_attachments(db, doc_json):
    if '_attachments' not in doc_json:
        return doc_json
    else:
        return db.get(doc_json['_id'], attachments=True)


def bulk_migrate(source_db, target_db, doc_types):

    with IterDB(target_db, new_edits=False, chunksize=25) as iter_db:
        for doc in get_all_docs_with_doc_types(source_db, doc_types):
            # It turns out that Cloudant does not support attachments=true
            # on views or on _all_docs, only on single doc gets, so we have
            # to manually re-query for the full doc + attachments.
            # (And I think there's literally no other way.)
            doc = _insert_attachments(source_db, doc)
            iter_db.save(doc)
