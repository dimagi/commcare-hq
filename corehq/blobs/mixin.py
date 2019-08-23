from __future__ import absolute_import
from __future__ import unicode_literals
import re
import sys
import uuid
from collections import defaultdict
from contextlib import contextmanager
from contextlib2 import ExitStack
from io import BytesIO
from hashlib import sha1
from itertools import chain
from os.path import join

from corehq.blobs import get_blob_db, CODES  # noqa: F401
from corehq.blobs.exceptions import AmbiguousBlobStorageError, NotFound
from corehq.blobs.util import (
    classproperty,
    document_method,
    random_url_id,
    SAFENAME,
)
from corehq.util.io import ClosingContextProxy
from couchdbkit.exceptions import InvalidAttachment, ResourceNotFound
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    DictProperty,
    IntegerProperty,
    StringProperty,
)
from memoized import memoized
import six


class BlobMetaRef(DocumentSchema):
    key = StringProperty()
    blobmeta_id = IntegerProperty()
    content_type = StringProperty()
    content_length = IntegerProperty()

    @classmethod
    def _from_attachment(cls, data):
        return cls(
            content_type=data.get("content_type"),
            content_length=data.get("length"),
        )

    @staticmethod
    def _normalize_json(dbname, doc_id, data):
        if "key" in data:
            return data
        return {
            "key": join(dbname, safe_id(doc_id), data["id"]),
            "content_length": data.get("content_length"),
            "content_type": data.get("content_type"),
        }


class BlobMixin(Document):

    class Meta(object):
        abstract = True

    # TODO evaluate all uses of `external_blobs`
    external_blobs = DictProperty(BlobMetaRef)

    # When true, fallback to couch on fetch and delete if blob is not
    # found in blobdb. Set this to True on subclasses that are in the
    # process of being migrated. When this is false (the default) the
    # methods on this mixin will not touch couchdb.
    _migrating_blobs_from_couch = False

    _atomic_blobs = None

    @classmethod
    def wrap(cls, data):
        if data.get("external_blobs"):
            doc_id = safe_id(data["_id"])
            dbname = _get_couchdb_name(cls)
            normalize = BlobMetaRef._normalize_json
            blobs = {}
            normalized = False
            for key, value in data["external_blobs"].items():
                if value["doc_type"] == "BlobMetaRef":
                    blobs[key] = value
                else:
                    blobs[key] = normalize(dbname, data['_id'], value)
                    normalized = True
            if normalized:
                data = data.copy()
                data["external_blobs"] = blobs
        return super(BlobMixin, cls).wrap(data)

    @classproperty
    def _blobdb_type_code(cls):
        """Blob DB type code

        This is an abstract attribute that must be set on non-abstract
        subclasses of `BlobMixin`. Its value should be one of the codes
        in `corehq.blobs.CODES`.
        """
        raise NotImplementedError(
            "abstract class attribute %s._blobdb_type_code is missing" %
            cls.__name__
        )

    @property
    def blobs(self):
        """Get a dictionary of BlobMetaRef objects keyed by attachment name

        Includes CouchDB attachments if `_migrating_blobs_from_couch` is true.
        The returned value should not be mutated.
        """
        if not self._migrating_blobs_from_couch or not self._attachments:
            return self.external_blobs
        value = {name: BlobMetaRef._from_attachment(info)
            for name, info in six.iteritems(self._attachments)}
        value.update(self.external_blobs)
        return value

    @document_method
    def put_attachment(self, content, name=None, content_type=None,
                       content_length=None, domain=None, type_code=None):
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
        if self._id is None:
            raise ResourceNotFound("cannot put attachment on unidentified document")
        if hasattr(self, "domain"):
            if domain is not None and self.domain != domain:
                raise ValueError("domain mismatch: %s != %s" % (self.domain, domain))
            domain = self.domain
        elif domain is None:
            raise ValueError("domain attribute or argument is required")
        old_meta = self.blobs.get(name)

        if isinstance(content, six.text_type):
            content = BytesIO(content.encode("utf-8"))
        elif isinstance(content, bytes):
            content = BytesIO(content)

        # do we need to worry about BlobDB reading beyond content_length?
        meta = db.put(
            content,
            domain=domain or self.domain,
            parent_id=self._id,
            name=name,
            type_code=(self._blobdb_type_code if type_code is None else type_code),
            content_type=content_type,
        )
        self.external_blobs[name] = BlobMetaRef(
            key=meta.key,
            blobmeta_id=meta.id,
            content_type=content_type,
            content_length=meta.content_length,
        )
        if self._migrating_blobs_from_couch and self._attachments:
            self._attachments.pop(name, None)
        if self._atomic_blobs is None:
            self.save()
            if old_meta and old_meta.key:
                db.delete(key=old_meta.key)
        elif old_meta and old_meta.key:
            self._atomic_blobs[name].append(old_meta.key)
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
                key = self.external_blobs[name].key
            except KeyError:
                if self._migrating_blobs_from_couch:
                    return super(BlobMixin, self) \
                        .fetch_attachment(name, stream=stream)
                raise NotFound(name)
            blob = db.get(key=key)
        except NotFound:
            raise ResourceNotFound(
                "{model} {model_id} attachment: {name!r}".format(
                    model=type(self).__name__,
                    model_id=self._id,
                    name=name,
                ))
        if stream:
            return blob

        with blob:
            return blob.read()

    def has_attachment(self, name):
        return name in self.blobs

    def delete_attachment(self, name):
        if self._migrating_blobs_from_couch and self._attachments:
            deleted = bool(self._attachments.pop(name, None))
        else:
            deleted = False
        meta = self.external_blobs.pop(name, None)
        if meta is not None:
            if self._atomic_blobs is None:
                deleted = get_blob_db().delete(key=meta.key) or deleted
            else:
                self._atomic_blobs[name].append(meta.key)
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
                self._id = uuid.uuid4().hex
            old_external_blobs = dict(self.external_blobs)
            if self._migrating_blobs_from_couch:
                if self._attachments:
                    old_attachments = dict(self._attachments)
                else:
                    old_attachments = None
            atomicity = self._atomic_blobs
            self._atomic_blobs = new_deleted = defaultdict(list)
            db = get_blob_db()
            success = False
            try:
                yield
                (self.save if save is None else save)()
                success = True
            except:
                typ, exc, tb = sys.exc_info()
                # delete new blobs that were not saved
                for name, meta in six.iteritems(self.external_blobs):
                    old_meta = old_external_blobs.get(name)
                    if old_meta is None or meta.key != old_meta.key:
                        db.delete(key=meta.key)
                self.external_blobs = old_external_blobs
                if self._migrating_blobs_from_couch:
                    self._attachments = old_attachments
                six.reraise(typ, exc, tb)
            finally:
                self._atomic_blobs = atomicity
            if success:
                # delete replaced blobs
                deleted = set()
                blobs = self.blobs
                for name, meta in list(six.iteritems(old_external_blobs)):
                    if name not in blobs or meta.key != blobs[name].key:
                        db.delete(key=meta.key)
                        deleted.add(meta.key)
                # delete newly created blobs that were overwritten or deleted
                for key in chain.from_iterable(six.itervalues(new_deleted)):
                    if key not in deleted:
                        db.delete(key=key)
        return atomic_blobs_context()


class BlobHelper(object):
    """Helper to get/set blobs given a document dict and couch database

    NOTE: attachments will be stored in couch and will be inaccessible
    using the normal attachments API if this is used to copy a document
    having "_attachments" but not "external_blobs" to a database in
    which the "doc_type" uses external blob storage and is not in
    `_migrating_blobs_from_couch` mode. To work around this limitation,
    put `"external_blobs": {}` in documents having a "doc_type" that
    uses external blob storage. The same is true when copying a document
    with "external_blobs" to a database that is not using an external
    blob database. To work around that, remove the "external_blobs" item
    from the document (after fetching all blobs) and be sure that the
    document has an "_attachments" value that is not `None`.

    Modifying "_attachments" or "external_blobs" values in a document is
    not recommended while it is wrapped in this class.
    """

    def __init__(self, doc, database, type_code):
        if doc.get("_id") is None:
            raise TypeError("BlobHelper requires a real _id")
        self._id = doc["_id"]
        self.doc = doc
        self.doc_type = doc["doc_type"]
        if "domain" in doc:
            self.domain = doc["domain"]
        elif self.doc_type == "Domain":
            self.domain = doc["name"]
        self._blobdb_type_code = type_code
        self.database = database
        self.couch_only = "external_blobs" not in doc
        self._migrating_blobs_from_couch = bool(doc.get("_attachments")) \
            and not self.couch_only
        self._attachments = doc.get("_attachments")
        self.external_blobs = {n: BlobMetaRef.wrap(
            BlobMetaRef._normalize_json(database.dbname, self._id, m.copy())
        ) for n, m in six.iteritems(doc.get("external_blobs", {}))}

    def __repr__(self):
        return "<%s %s domain=%s id=%s>" % (
            type(self).__name__,
            self.doc_type,
            getattr(self, "domain", ""),
            self._id,
        )

    _atomic_blobs = None

    @property
    def blobs(self):
        return BlobMixin.blobs.fget(self)

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
                        for name, meta in six.iteritems(self.external_blobs)}
                    raise
        return context()

    def _sync_doc(self):
        if "_attachments" in self.doc:
            assert self.doc["_attachments"] == self._attachments
        if "external_blobs" in self.doc:
            # because put_attachment calls self.save()
            self.doc["external_blobs"] = {name: meta.to_json()
                for name, meta in six.iteritems(self.external_blobs)}

    def save(self):
        self._sync_doc()
        self.database.save_doc(self.doc)


class DeferredBlobMixin(BlobMixin):
    """Similar to BlobMixin, but can defer attachment puts until save

    This class is intended for backward compatibility with code that set
    `_attachments` to a dict of attachments with content. It is not
    recommended to use this in new code.
    """

    class Meta(object):
        abstract = True

    _deferred_blobs = None

    @property
    def blobs(self):
        value = super(DeferredBlobMixin, self).blobs
        if self._deferred_blobs:
            value = dict(value)
            for name, info in six.iteritems(self._deferred_blobs):
                if info is not None:
                    value[name] = BlobMetaRef(
                        key=None,
                        content_type=info.get("content_type", None),
                        content_length=info.get("content_length", None),
                    )
                else:
                    value.pop(name, None)
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
            if self._deferred_blobs[name] is None:
                raise ResourceNotFound(
                    "{model} {model_id} attachment: {name!r}".format(
                        model=type(self).__name__,
                        model_id=self._id,
                        name=name,
                    ))
            body = self._deferred_blobs[name]["content"]
            if stream:
                return ClosingContextProxy(BytesIO(body))
            return body
        return super(DeferredBlobMixin, self).fetch_attachment(name, stream)

    def delete_attachment(self, name):
        if self._deferred_blobs:
            deleted = bool(self._deferred_blobs.pop(name, None))
        else:
            deleted = False
        return super(DeferredBlobMixin, self).delete_attachment(name) or deleted

    def deferred_put_attachment(self, content, name=None, content_type=None,
                                content_length=None, domain=None, type_code=None):
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
        if isinstance(content, six.text_type):
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
            "domain": domain or getattr(self, "domain", None),
            "type_code": type_code,
        }

    def deferred_delete_attachment(self, name):
        """Mark attachment to be deleted on save"""
        if self._deferred_blobs is None:
            self._deferred_blobs = {}
        self._deferred_blobs[name] = None

    def save(self):
        if self._deferred_blobs:
            delete_names = []
            with self.atomic_blobs(super(DeferredBlobMixin, self).save):
                # list deferred blobs to avoid modification during iteration
                for name, info in list(six.iteritems(self._deferred_blobs)):
                    if info is not None:
                        self.put_attachment(name=name, **info)
                    else:
                        delete_names.append(name)
            for name in delete_names:
                self.delete_attachment(name)
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
    with ExitStack() as stack:
        for mgr in contexts:
            stack.enter_context(mgr)
        delete_blobs = []
        for doc in docs:
            if isinstance(doc, DeferredBlobMixin) and doc._deferred_blobs:
                for name, info in list(six.iteritems(doc._deferred_blobs)):
                    if info is not None:
                        doc.put_attachment(name=name, **info)
                    else:
                        meta = doc.external_blobs.pop(name, None)
                        if meta is not None:
                            delete_blobs.append(meta.key)
                        doc._deferred_blobs.pop(name)
                assert not doc._deferred_blobs, doc._deferred_blobs
        yield
        db = get_blob_db()
        for key in delete_blobs:
            db.delete(key=key)


@memoized
def _get_couchdb_name(doc_class):
    return doc_class.get_db().dbname


def safe_id(identifier):
    if not SAFENAME.match(identifier):
        identifier = 'sha1-' + sha1(identifier.encode('utf-8')).hexdigest()
    elif SHA1_ID.match(identifier):
        # could collide with "safe" id and should never happen anyway
        raise ValueError("illegal doc id: {!r}".format(identifier))
    return identifier


SHA1_ID = re.compile("sha1-[0-9a-f]{40}$")
