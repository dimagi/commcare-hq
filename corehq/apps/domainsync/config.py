from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound
from corehq.blobs.mixin import BlobHelper, CODES


COUCH_DOC_TYPE_CODES = {
    "CommCareBuild": CODES.commcarebuild,
    "Domain": CODES.domain,
    "InvoicePdf": CODES.invoice,

    "CommCareCase": CODES._default,
    "CommCareCase-deleted": CODES._default,
    "CommCareCase-Deleted": CODES._default,
    "CommCareCase-Deleted-Deleted": CODES._default,

    "Application": CODES.application,
    "Application-Deleted": CODES.application,
    "LinkedApplication": CODES.application,
    "RemoteApp": CODES.application,
    "RemoteApp-Deleted": CODES.application,
    "SavedAppBuild": CODES.application,

    "ExportInstance": CODES.data_export,
    "CaseExportInstance": CODES.data_export,
    "FormExportInstance": CODES.data_export,
    "SMSExportInstance": CODES.data_export,

    "XFormInstance": CODES.form_xml,
    "XFormInstance-Deleted": CODES.form_xml,
    "XFormArchived": CODES.form_xml,
    "XFormDeprecated": CODES.form_xml,
    "XFormDuplicate": CODES.form_xml,
    "XFormError": CODES.form_xml,
    "SubmissionErrorLog": CODES.form_xml,
    "HQSubmission": CODES.form_xml,

    "CommCareAudio": CODES.multimedia,
    "CommCareImage": CODES.multimedia,
    "CommCareVideo": CODES.multimedia,
    "CommCareMultimedia": CODES.multimedia,
}


class DocumentTransform(object):
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
                obj = BlobHelper(doc, database, None)
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
        except ResourceNotFound:
            # this is likely a document that was deleted locally that
            # you later want to copy back over there is a wacky hack
            # that you can use to handle this
            rev = get_deleted_doc_rev(database, transform.doc['_id'])
            transform.doc['_rev'] = rev
            database.save_doc(transform.doc)
    if transform.attachments:
        type_code = COUCH_DOC_TYPE_CODES[transform.doc["doc_type"]]
        obj = BlobHelper(transform.doc, database, type_code)
        with obj.atomic_blobs(save):
            for name, attach in transform.attachments.items():
                content_type = transform._attachments[name]["content_type"]
                obj.put_attachment(attach, name, content_type=content_type)
    else:
        save()


def get_deleted_doc_rev(database, id):
    # strange couch voodoo magic for deleted docs
    return database.get(id, open_revs="all")[0]['ok']['_rev']
