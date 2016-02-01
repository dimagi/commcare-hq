import base64
import json

from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.util.couch import IterDB


def _encode_data(attachment_dict):
    data = attachment_dict['data']
    # couchdbkit is annoying and auto-converts
    # anything that looks like utf-8 to unicode
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    attachment_dict['data'] = base64.b64encode(data)
    return attachment_dict


def _insert_attachments(db, doc_json):
    if '_attachments' not in doc_json:
        return
    else:
        full_doc = db.get(doc_json['_id'], attachments=True)
        doc_json['_attachments'] = {
            name: _encode_data(attachment_dict)
            for name, attachment_dict in full_doc['_attachments'].items()
        }


def bulk_migrate(source_db, target_db, doc_types, filename):

    with open(filename, 'w') as f:
        for doc in get_all_docs_with_doc_types(source_db, doc_types):
            # It turns out that Cloudant does not support attachments=true
            # on views or on _all_docs, only on single doc gets
            # instead, we have to fetch each attachment individually
            # (And I think there's literally no other way.)
            _insert_attachments(source_db, doc)
            f.write('{}\n'.format(json.dumps(doc)))

    with open(filename, 'r') as f:
        with IterDB(target_db, new_edits=False) as iter_db:
            for line in f:
                doc = json.loads(line)
                iter_db.save(doc)
