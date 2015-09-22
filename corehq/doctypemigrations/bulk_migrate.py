import json
from corehq.util.couch import IterDB
from corehq.util.couch_helpers import paginate_view


def _get_all_docs_with_doc_types(db, doc_types):
    for doc_type in doc_types:
        results = paginate_view(
            db, 'all_docs/by_doc_type',
            chunk_size=100, startkey=[doc_type], endkey=[doc_type, {}],
            attachments=True, include_docs=True, reduce=False)
        for result in results:
            yield result['doc']


def bulk_migrate(source_db, target_db, doc_types, filename):

    with open(filename, 'w') as f:
        for doc in _get_all_docs_with_doc_types(source_db, doc_types):
            f.write('{}\n'.format(json.dumps(doc)))

    with open(filename, 'r') as f:
        with IterDB(target_db, new_edits=False) as iter_db:
            for line in f:
                doc = json.loads(line)
                iter_db.save(doc)
