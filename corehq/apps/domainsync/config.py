from couchdbkit import ResourceNotFound
from corehq.blobs.mixin import BlobHelper


class DocumentTransform():
    # for coupling reasons, we have to bundle the original document
    # with its attachments so that we can properly deal with it
    # across databases.
    # We also need the source database to fetch the attachment

    def __init__(self, doc, database, exclude_attachments=False):
        self._attachments = {}
        self.attachments = {}
        self.database = database
        _attachments = doc.get("_attachments", None) or {}
        _attachments.update(doc.get("external_blobs", None) or {})
        if _attachments:
            if not exclude_attachments:
                self._attachments = _attachments
                obj = BlobHelper(doc, database)
                self.attachments = {k: obj.fetch_attachment(k) for k in _attachments}
            if doc.get("_attachments"):
                doc["_attachments"] = {}
            if "external_blobs" in doc:
                doc["external_blobs"] = {}
        self.doc = doc
        del self.doc['_rev']


def save(transform, database):
    # this is a fancy save method because we do some special casing
    # with the attachments and with deleted documents
    def save():
        try:
            database.save_doc(transform.doc, force_update=True)
        except ResourceNotFound, e:
            # this is likely a document that was deleted locally that
            # you later want to copy back over there is a wacky hack
            # that you can use to handle this
            rev = get_deleted_doc_rev(database, transform.doc['_id'])
            transform.doc['_rev'] = rev
            database.save_doc(transform.doc)
    if transform.attachments:
        obj = BlobHelper(doc, database)
        with obj.atomic_blobs(save):
            for name, attach in transform.attachments.items():
                content_type = transform._attachments[name]["content_type"]
                obj.put_attachment(attach, name, content_type=content_type)
    else:
        save()


def get_deleted_doc_rev(database, id):
    # strange couch voodoo magic for deleted docs
    return database.get(id, open_revs="all")[0]['ok']['_rev']
