import json
import os
from cStringIO import StringIO
from tempfile import mkdtemp

from couchexport.models import SavedBasicExport
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.util.couch import IterDB

class Migrator(object):

    def __init__(self, doc_types):
        self.doc_types = doc_types

    def migrate(self, filename):
        return migrate(self.doc_types, filename)


MIGRATIONS = {
    "saved_exports": Migrator(
        doc_types=[SavedBasicExport],
    ),
}


def migrate(doc_types, filename=None):
    """Migrate attachments from couchdb to blob storage

    The blob storage backend is associated with the model class.

    :param doc_types: List of couch model classes with attachments to be migrated.
    :param filename: File path for intermediate storage of migration data.
    """
    couchdb = doc_types[0].get_db()
    assert all(t.get_db() is couchdb for t in doc_types[1:]), repr(doc_types)
    type_map = {cls.__name__: cls for cls in doc_types}

    dirpath = None
    if filename is None:
        dirpath = mkdtemp()
        filename = os.path.join(dirpath, "export.txt")

    print("Loading {} documents...".format(", ".join(type_map)))
    total = 0
    with open(filename, 'w') as f:
        for doc in get_all_docs_with_doc_types(couchdb, list(type_map)):
            if doc.get("_attachments"):
                f.write('{}\n'.format(json.dumps(doc)))
                total += 1

    with IterDB(couchdb) as iter_db, open(filename, 'r') as f:
        for n, line in enumerate(f):
            if n % 100 == 0:
                print_status(n + 1, total)
            doc = json.loads(line)
            obj = type_map[doc["doc_type"]](doc)
            for name, meta in obj._attachments.iteritems():
                content = StringIO(meta["data"].decode("base64"))
                obj.put_attachment(
                        content, name, content_type=meta["content_type"])

            # delete couch attachments - http://stackoverflow.com/a/2750476
            obj._attachments.clear()

            iter_db.save(obj.to_json())

    if dirpath is not None:
        os.remove(filename)
        os.rmdir(dirpath)

    print("Migrated {} documents with attachments. Done.".format(total))
    return total


def print_status(num, total):
    print("Migrating {} of {} documents with attachments".format(num, total))
