from __future__ import absolute_import
import re
import sys
from collections import defaultdict
from contextlib import contextmanager, nested
from cStringIO import StringIO
from hashlib import sha1
from itertools import chain
from os.path import join

from corehq.blobs import BlobInfo, get_blob_db
from corehq.blobs.exceptions import AmbiguousBlobStorageError, NotFound
from corehq.blobs.interface import SAFENAME
from corehq.blobs.util import ClosingContextProxy, document_method, random_url_id
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

    @property
    def info(self):
        return BlobInfo(self.id, self.content_length, self.digest)


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
        return join(_get_couchdb_name(type(self)), safe_id(self._id))

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

    @document_method
    def put_attachment(self, content, name=None, content_type=None, content_length=None):
        """Put attachment in blob database

        See `get_short_identifier()` for restrictions on the upper bound
        for number of attachments per object.

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
        info = db.put(content, get_short_identifier(), bucket=bucket)
        self.external_blobs[name] = BlobMeta(
            id=info.identifier,
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

    @document_method
    def fetch_attachment(self, name, stream=False):
        """Get named attachment

        :param stream: When true, return a file-like object that can be
        read at least once (streamers should not expect to seek within
        or read the contents of the returned file more than once).
        """
        db = get_blob_db()
        try:
            try:
                meta = self.external_blobs[name]
            except KeyError:
                if self.migrating_blobs_from_couch:
                    return super(BlobMixin, self) \
                        .fetch_attachment(name, stream=stream)
                raise NotFound
            blob = db.get(meta.id, self._blobdb_bucket())
        except NotFound:
            raise ResourceNotFound(
                u"{model} {model_id} attachment: {name!r}".format(
                    model=type(self).__name__,
                    name=name,
                    model_id=self._id,
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

    def has_attachment(self, name):
        return name in self.blobs

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

    @document_method
    def atomic_blobs(self, save=None):
        """Return a context manager to atomically save doc + blobs

        Usage::

            with doc.atomic_blobs():
                doc.put_attachment(...)
            # doc and blob are now saved

        Blobs saved inside the context manager will be deleted if an
        exception is raised inside the context body.

        :param save: A function to be called instead of `self.save()`
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
                (self.save if save is None else save)()
                success = True
            except:
                typ, exc, tb = sys.exc_info()
                # delete new blobs that were not saved
                for name, meta in self.external_blobs.iteritems():
                    old_meta = old_external_blobs.get(name)
                    if old_meta is None or meta.id != old_meta.id:
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
                blobs = self.blobs
                for name, meta in list(old_external_blobs.iteritems()):
                    if name not in blobs or meta.id != blobs[name].id:
                        db.delete(meta.id, bucket)
                        deleted.add(meta.id)
                # delete newly created blobs that were overwritten or deleted
                for meta in chain.from_iterable(new_deleted.itervalues()):
                    if meta.id not in deleted:
                        db.delete(meta.id, bucket)
        return atomic_blobs_context()


class BlobHelper(object):
    """Helper to get/set blobs given a document dict and couch database

    NOTE: attachments will be stored in couch and will be inaccessible
    using the normal attachments API if this is used to copy a document
    having "_attachments" but not "external_blobs" to a database in
    which the "doc_type" uses external blob storage and is not in
    `migrating_blobs_from_couch` mode. To work around this limitation,
    put `"external_blobs": {}` in documents having a "doc_type" that
    uses external blob storage. The same is true when copying a document
    with "external_blobs" to a database that is not using an external
    blob database. To work around that, remove the "external_blobs" item
    from the document (after fetching all blobs) and be sure that the
    document has an "_attachments" value that is not `None`.

    Modifying "_attachments" or "external_blobs" values in a document is
    not recommended while it is wrapped in this class.
    """

    def __init__(self, doc, database):
        if doc.get("_id") is None:
            raise TypeError("BlobHelper requires a real _id")
        self._id = doc["_id"]
        self.doc = doc
        self.database = database
        self.couch_only = "external_blobs" not in doc
        self.migrating_blobs_from_couch = bool(doc.get("_attachments")) \
            and not self.couch_only
        self._attachments = doc.get("_attachments")
        blobs = doc.get("external_blobs", {})
        self.external_blobs = {n: BlobMeta.wrap(m.copy())
                               for n, m in blobs.iteritems()}

    _atomic_blobs = None

    @property
    def blobs(self):
        return BlobMixin.blobs.fget(self)

    def _blobdb_bucket(self):
        return join(self.database.dbname, safe_id(self._id))

    def put_attachment(self, content, name=None, *args, **kw):
        if self._attachments is None and self.couch_only:
            raise AmbiguousBlobStorageError(" ".join("""
                Ambiguous blob storage: doc has no _attachments and no
                external_blobs. Put a dict (may be empty) in one or both
                to indicate where blobs are located (_attachments ->
                couch, external_blobs -> blob db). If both are present,
                new blobs will be stored in the blob db, but existing
                blobs will be fetched from couch if there is no
                corresponding key in the external_blobs dict.
            """.split()))
        if self.couch_only:
            self.database.put_attachment(self.doc, content, name, *args, **kw)
        else:
            BlobMixin.put_attachment(self, content, name, *args, **kw)
            self._sync_doc()
        return True

    def fetch_attachment(self, name, *args, **kw):
        if name in self.external_blobs:
            return BlobMixin.fetch_attachment(self, name, *args, **kw)
        return self.database.fetch_attachment(self._id, name, *args, **kw)

    def delete_attachment(self, *args, **kw):
        raise NotImplementedError

    def atomic_blobs(self, save=None):
        if save is not None:
            original_save = save

            def save():
                self._sync_doc()
                original_save()

        if self.couch_only:
            @contextmanager
            def context():
                (self.save if save is None else save)()
                yield
        else:
            @contextmanager
            def context():
                try:
                    with BlobMixin.atomic_blobs(self, save):
                        yield
                except:
                    self.doc["_attachments"] = self._attachments
                    self.doc["external_blobs"] = {name: meta.to_json()
                        for name, meta in self.external_blobs.iteritems()}
                    raise
        return context()

    def _sync_doc(self):
        if "_attachments" in self.doc:
            assert self.doc["_attachments"] == self._attachments
        if "external_blobs" in self.doc:
            # because put_attachment calls self.save()
            self.doc["external_blobs"] = {name: meta.to_json()
                for name, meta in self.external_blobs.iteritems()}

    def save(self):
        self._sync_doc()
        self.database.save_doc(self.doc)


class DeferredBlobMixin(BlobMixin):
    """Similar to BlobMixin, but can defer attachment puts until save

    This class is intended for backward compatibility with code that set
    `_attachments` to a dict of attachments with content. It is not
    recommended to use this in new code.
    """

    class Meta:
        abstract = True

    _deferred_blobs = None

    @property
    def blobs(self):
        value = super(DeferredBlobMixin, self).blobs
        if self._deferred_blobs:
            value = dict(value)
            value.update((name, BlobMeta(
                id=None,
                content_type=info.get("content_type", None),
                content_length=info.get("content_length", None),
                digest=None,
            )) for name, info in self._deferred_blobs.iteritems())
        return value

    @property
    def persistent_blobs(self):
        """Get a dict like `blobs` containing only non-deferred items"""
        value = super(DeferredBlobMixin, self).blobs
        if self._deferred_blobs:
            value = value.copy()
            for name in self._deferred_blobs:
                value.pop(name, None)
        return value

    def put_attachment(self, content, name=None, *args, **kw):
        if self._deferred_blobs:
            self._deferred_blobs.pop(name, None)
        return super(DeferredBlobMixin, self).put_attachment(content, name,
                                                             *args, **kw)

    def fetch_attachment(self, name, stream=False):
        if self._deferred_blobs and name in self._deferred_blobs:
            body = self._deferred_blobs[name]["content"]
            if stream:
                return ClosingContextProxy(StringIO(body))
            try:
                body = body.decode("utf-8", "strict")
            except UnicodeDecodeError:
                # Return bytes on decode failure, otherwise unicode.
                # Ugly, but consistent with restkit.wrappers.Response.body_string
                pass
            return body
        return super(DeferredBlobMixin, self).fetch_attachment(name, stream)

    def delete_attachment(self, name):
        if self._deferred_blobs:
            deleted = bool(self._deferred_blobs.pop(name, None))
        else:
            deleted = False
        return super(DeferredBlobMixin, self).delete_attachment(name) or deleted

    def deferred_put_attachment(self, content, name=None, content_type=None,
                                content_length=None):
        """Queue attachment to be persisted on save

        WARNING this loads the entire blob content into memory. Use of
        this method is discouraged:

        - Generally it is bad practice to load large blobs into memory
          in their entirety. Ideally blobs should be streamed between
          the client and the blob database.
        - JSON serialization becomes less efficient because blobs are
          base-64 encoded, requiring even more memory.

        This method takes the same parameters as `put_attachment`.
        """
        if isinstance(content, unicode):
            content = content.encode('utf-8')
        elif not isinstance(content, bytes):
            content = content.read()
        if self._deferred_blobs is None:
            self._deferred_blobs = {}
        length = len(content) if content_length is None else content_length
        self._deferred_blobs[name] = {
            "content": content,
            "content_type": content_type,
            "content_length": length,
        }

    def save(self):
        if self._deferred_blobs:
            with self.atomic_blobs(super(DeferredBlobMixin, self).save):
                # list deferred blobs to avoid modification during iteration
                for name, info in list(self._deferred_blobs.iteritems()):
                    self.put_attachment(name=name, **info)
                assert not self._deferred_blobs, self._deferred_blobs
        else:
            super(DeferredBlobMixin, self).save()


def get_short_identifier():
    """Get a short random identifier

    The identifier is chosen from a 64 bit key space, which is suitably
    large for no likely collisions in 1000 concurrent keys but kept
    small to minimize key length. 1000 is an arbitrary number chosen as
    an upper bound of the number of attachments associated with any
    given object. We may need to change this if we ever expect an object
    to have significantly more than 1000 attachments. The probability of
    a collision with a 64 bit ID is:

    k = 1000
    N = 2 ** 64
    (k ** 2) / (2 * N) = 2.7e-14

    which is somewhere near the probability of a meteor landing on
    your house. For most objects the number of blobs present at any
    moment in time will be far lower, and therefore the probability
    of a collision will be much lower as well.

    http://preshing.com/20110504/hash-collision-probabilities/
    """
    return random_url_id(8)


@contextmanager
def bulk_atomic_blobs(docs):
    """Atomic blobs persistence to be used with ``db.bulk_save(docs)``

    Blobs may be added to or deleted from objects within the context
    body. Blobs previously added with
    ``DeferredBlobMixin.deferred_put_attachment`` will be persisted
    automatically. NOTE this method will persist attachments, but it
    does not save the documents to couch. Call `db.bulk_save(docs)`
    within the context to do that.

    :param docs: A list of model objects.
    """
    save = lambda: None
    contexts = [d.atomic_blobs(save) for d in docs if hasattr(d, "atomic_blobs")]
    with nested(*contexts):
        for doc in docs:
            if isinstance(doc, DeferredBlobMixin) and doc._deferred_blobs:
                for name, info in list(doc._deferred_blobs.iteritems()):
                    doc.put_attachment(name=name, **info)
                assert not doc._deferred_blobs, doc._deferred_blobs
        yield


@memoized
def _get_couchdb_name(doc_class):
    return doc_class.get_db().dbname


def safe_id(identifier):
    if not SAFENAME.match(identifier):
        identifier = u'sha1-' + sha1(identifier.encode('utf-8')).hexdigest()
    elif SHA1_ID.match(identifier):
        # could collide with "safe" id and should never happen anyway
        raise ValueError("illegal doc id: {!r}".format(identifier))
    return identifier


SHA1_ID = re.compile("sha1-[0-9a-f]{40}$")
