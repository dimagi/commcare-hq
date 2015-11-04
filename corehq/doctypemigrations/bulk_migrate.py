import json

from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.util.couch import IterDB


def bulk_migrate(source_db, target_db, doc_types, filename):

    with open(filename, 'w') as f:
        for doc in get_all_docs_with_doc_types(source_db, doc_types):
            f.write('{}\n'.format(json.dumps(doc)))

    with open(filename, 'r') as f:
        with IterDB(target_db, new_edits=False) as iter_db:
            for line in f:
                doc = json.loads(line)
                iter_db.save(doc)
