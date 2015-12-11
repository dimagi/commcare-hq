import base64
import json

from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.util.couch import IterDB


def fetch_binary_attachment(db, doc_id, name):
    data = db.fetch_attachment(doc_id, name)
    # couchdbkit is annoying and auto-converts
    # anything that looks like utf-8 to unicode
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    return data


def insert_attachment(db, doc_json):
    """
    fetch attachment bodies for doc_json with attachment stubs
    and insert them into the doc_json

    """
    if '_attachments' not in doc_json:
        return
    else:
        for name, value in doc_json['_attachments'].items():
            # it's a bit of a wash whether to fetch attachments individually
            # or re-fetch the whole doc with attachments.
            # For a doc with a single attachment this is faster,
            # so I'll go with it for now
            data = fetch_binary_attachment(db, doc_json['_id'], name)
            doc_json['_attachments'][name] = {
                'data': base64.b64encode(data),
                'length': value['length'],
                'content_type': value['content_type'],
                'digest': value['digest'],
                'revpos': value['revpos']
            }


def bulk_migrate(source_db, target_db, doc_types, filename):

    with open(filename, 'w') as f:
        for doc in get_all_docs_with_doc_types(source_db, doc_types):
            # It turns out that Cloudant does not support attachments=true
            # on views or on _all_docs, only on single doc gets
            # instead, we have to fetch each attachment individually
            # (And I think there's literally no other way.)
            insert_attachment(source_db, doc)
            f.write('{}\n'.format(json.dumps(doc)))

    with open(filename, 'r') as f:
        with IterDB(target_db, new_edits=False) as iter_db:
            for line in f:
                doc = json.loads(line)
                iter_db.save(doc)
