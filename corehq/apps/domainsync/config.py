from couchdbkit import ResourceNotFound


class DocumentTransform():
    # for coupling reasons, we have to bundle the original document
    # with its attachments so that we can properly deal with it
    # across databases.
    # We also need the source database to fetch the attachment
    def __init__(self, doc, database, exclude_attachments=False):
        self._attachments = {}
        self.attachments = {}
        self.database = database
        if "_attachments" in doc and doc['_attachments']:
            _attachments = doc.pop("_attachments")
            if not exclude_attachments:
                self._attachments = _attachments
                self.attachments = dict((k, self.database.fetch_attachment(doc["_id"], k)) for k in self._attachments)
        self.doc = doc
        del self.doc['_rev']


def save(transform, database):
    # this is a fancy save method because we do some special casing
    # with the attachments and with deleted documents
    try:
        database.save_doc(transform.doc, force_update=True)
    except ResourceNotFound, e:
        # this is likely a document that was deleted locally that you later want to copy back over
        # there is a wacky hack that you can use to handle this
        rev = get_deleted_doc_rev(database, transform.doc['_id'])
        transform.doc['_rev'] = rev
        database.save_doc(transform.doc)
    for k, attach in transform.attachments.items():
        database.put_attachment(transform.doc, attach, name=k,
                                content_type=transform._attachments[k]["content_type"])


def get_deleted_doc_rev(database, id):
    # strange couch voodoo magic for deleted docs
    return database.get(id, open_revs="all")[0]['ok']['_rev']
