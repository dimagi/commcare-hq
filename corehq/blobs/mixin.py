from __future__ import absolute_import
import sys
from cStringIO import StringIO
from itertools import chain
from os.path import join
from collections import defaultdict
from contextlib import contextmanager

from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound
from couchdbkit.exceptions import InvalidAttachment, ResourceNotFound
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    DictProperty,
    IntegerProperty,
    StringProperty,
)
from dimagi.utils.decorators.memoized import memoized


class BlobMeta(DocumentSchema):
    id = StringProperty()
    content_type = StringProperty()
    content_length = IntegerProperty()
    digest = StringProperty()


class BlobMixin(Document):

    class Meta:
        abstract = True

    external_blobs = DictProperty(BlobMeta)

    # When true, fallback to couch on fetch and delete if blob is not
    # found in blobdb. Set this to True on subclasses that are in the
    # process of being migrated. When this is false (the default) the
    # methods on this mixin will not touch couchdb.
    migrating_blobs_from_couch = False

    _atomic_blobs = None

    def _blobdb_bucket(self):
        if self._id is None:
            raise ResourceNotFound(
                "cannot manipulate attachment on unidentified document")
        return join(_get_couchdb_name(type(self)), self._id)

    @property
    def blobs(self):
        """Get a dictionary of BlobMeta objects keyed by attachment name

        Includes CouchDB attachments if `migrating_blobs_from_couch` is true.
        The returned value should not be mutated.
        """
        if not self.migrating_blobs_from_couch or not self._attachments:
            return self.external_blobs
        value = {name: BlobMeta(
            id=None,
            content_length=info.get("length", None),
            content_type=info.get("content_type", None),
            digest=info.get("digest", None),
        ) for name, info in self._attachments.iteritems()}
        value.update(self.external_blobs)
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
        old_meta = self.blobs.get(name)

        if isinstance(content, unicode):
            content = StringIO(content.encode("utf-8"))
        elif isinstance(content, bytes):
            content = StringIO(content)

        bucket = self._blobdb_bucket()
        # do we need to worry about BlobDB reading beyond content_length?
        info = db.put(content, name, bucket)
        self.external_blobs[name] = BlobMeta(
            id=info.name,
            content_type=content_type,
            content_length=info.length,
            digest=info.digest,
        )
        if self.migrating_blobs_from_couch and self._attachments:
            self._attachments.pop(name, None)
        if self._atomic_blobs is None:
            self.save()
            if old_meta and old_meta.id:
                db.delete(old_meta.id, bucket)
        elif old_meta and old_meta.id:
            self._atomic_blobs[name].append(old_meta)
        return True

    def fetch_attachment(self, name, stream=False):
        """Get named attachment

        :param stream: When true, return a file-like object that can be
        read at least once (streamers should not expect to seek within
        or read the contents of the returned file more than once).
        """
        db = get_blob_db()
        try:
            meta = self.external_blobs[name]
            blob = db.get(meta.id, self._blobdb_bucket())
        except (KeyError, NotFound):
            if self.migrating_blobs_from_couch:
                return super(BlobMixin, self).fetch_attachment(name, stream=stream)
            raise ResourceNotFound(u"{model} attachment: {name!r}".format(
                                   model=type(self).__name__, name=name))
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
        if self.migrating_blobs_from_couch and self._attachments:
            deleted = bool(self._attachments.pop(name, None))
        else:
            deleted = False
        meta = self.external_blobs.pop(name, None)
        if meta is not None:
            if self._atomic_blobs is None:
                bucket = self._blobdb_bucket()
                deleted = get_blob_db().delete(meta.id, bucket) or deleted
            else:
                self._atomic_blobs[name].append(meta)
                deleted = True
        if self._atomic_blobs is None:
            self.save()
        return deleted

    def atomic_blobs(self):
        """Return a context manager to atomically save doc + blobs

        Usage::

            with doc.atomic_blobs():
                doc.put_attachment(...)
            # doc and blob are now saved

        Blobs saved inside the context manager will be deleted if an
        exception is raised inside the context body.
        """
        @contextmanager
        def atomic_blobs_context():
            if self._id is None:
                self._id = self.get_db().server.next_uuid()
            old_external_blobs = dict(self.external_blobs)
            if self.migrating_blobs_from_couch:
                if self._attachments:
                    old_attachments = dict(self._attachments)
                else:
                    old_attachments = None
            atomicity = self._atomic_blobs
            self._atomic_blobs = new_deleted = defaultdict(list)
            db = get_blob_db()
            bucket = self._blobdb_bucket()
            success = False
            try:
                yield
                self.save()
                success = True
            except:
                typ, exc, tb = sys.exc_info()
                # delete new blobs that were not saved
                for name, meta in self.external_blobs.iteritems():
                    if meta is not old_external_blobs.get(name):
                        db.delete(meta.id, bucket)
                self.external_blobs = old_external_blobs
                if self.migrating_blobs_from_couch:
                    self._attachments = old_attachments
                raise typ, exc, tb
            finally:
                self._atomic_blobs = atomicity
            if success:
                # delete replaced blobs
                deleted = set()
                for name, meta in list(old_external_blobs.iteritems()):
                    if meta is not self.blobs.get(name):
                        db.delete(meta.id, bucket)
                        deleted.add(meta.id)
                # delete newly created blobs that were overwritten or deleted
                for meta in chain.from_iterable(new_deleted.itervalues()):
                    if meta.id not in deleted:
                        db.delete(meta.id, bucket)
        return atomic_blobs_context()


@memoized
def _get_couchdb_name(doc_class):
    return doc_class.get_db().dbname
