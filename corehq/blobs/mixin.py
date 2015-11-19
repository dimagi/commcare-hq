from __future__ import absolute_import
from cStringIO import StringIO
from os.path import join

from corehq.blobs.fsdb import FilesystemBlobDB, NotFound
from couchdbkit.exceptions import InvalidAttachment, ResourceNotFound
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    DictProperty,
    IntegerProperty,
    StringProperty,
)
from django.conf import settings


class BlobMeta(DocumentSchema):
    content_type = StringProperty()
    content_length = IntegerProperty()


class BlobMixin(Document):

    _blobs = DictProperty(BlobMeta)

    # When true, fallback to couch on fetch and delete if blob is not
    # found in blobdb. Set this to True on subclasses that are in the
    # process of being migrated. When this is false (the default) the
    # methods on this mixin will not touch couchdb.
    _migrating_from_couch = False

    def _blobdb_bucket(self):
        if self._id is None or self._rev is None:
            raise ResourceNotFound("cannot manipulate attachment on unsaved document")
        return join(self.doc_type, self._id)

    @property
    def blobs(self):
        """Get a dictionary of BlobMeta objects keyed by attachment name

        Includes CouchDB attachments if `_migrating_from_couch` is true.
        The returned value should not be mutated.
        """
        if not self._migrating_from_couch:
            return self._blobs
        value = {name: BlobMeta(
            content_length=info["length"],
            content_type=info["content_type"],
        ) for name, info in self._attachments.iteritems()}
        value.update(self._blobs)
        return value

    def put_attachment(self, content, name=None, content_type=None, content_length=None):
        """Put attachment in blob database

        :param content: String or file object.
        """
        db = get_blob_db()

        if name is None:
            name = getattr(content, "name", None)
        if name is None:
            raise InvalidAttachment("cannot save attachment without name")

        if isinstance(content, unicode):
            content = StringIO(content.encode("utf-8"))
        elif isinstance(content, bytes):
            content = StringIO(content)

        # do we need to worry about BlobDB reading beyond content_length?
        bucket = self._blobdb_bucket()
        content_length = db.put(content, name, bucket)
        self._blobs[name] = BlobMeta(
            content_type=content_type,
            content_length=content_length,
        )
        return True

    def fetch_attachment(self, name, stream=False):
        """Get named attachment

        :param stream: When true, return a file-like object that can be
        read at least once (streamers should not expect to seek within
        or read the contents of the returned file more than once).
        """
        db = get_blob_db()
        try:
            blob = db.get(name, self._blobdb_bucket())
        except NotFound:
            if self._migrating_from_couch:
                # TODO remove this at some point in the future when all
                # attachments have been migrated from couch to blobdb.
                return super(BlobMixin, self).fetch_attachment(
                                                        name, stream=stream)
            raise ResourceNotFound(u"{model} attachment: {name!r}".format(
                model=type(self).__name__,
                name=name,
            ))
        if stream:
            return blob

        with blob:
            body = blob.read()
        try:
            body = body.decode("utf-8", "strict")
        except UnicodeDecodeError:
            # Return bytes on decode failure, otherwise unicode.
            # Ugly, but consistent with restkit.wrappers.Response.body_string
            pass
        return body

    def delete_attachment(self, name):
        if self._migrating_from_couch:
            # TODO remove this at some point in the future when all
            # attachments have been migrated from couch to blobdb.
            deleted = super(BlobMixin, self).delete_attachment(name)
        else:
            deleted = False
        return get_blob_db().delete(name, self._blobdb_bucket()) or deleted


_blob_db = [] # singleton/global, stack for tests to push temporary dbs

def get_blob_db():
    if not _blob_db:
        db = FilesystemBlobDB(settings.SHARED_DRIVE_CONF.blob_dir)
        _blob_db.append(db)
    return _blob_db[-1]
