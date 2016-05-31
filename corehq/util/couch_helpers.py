import base64
import datetime
import hashlib
import threading
from copy import copy
from mimetypes import guess_type

from couchdbkit import ResourceNotFound


class CouchAttachmentsBuilder(object):
    """
    Helper for saving attachments on doc save rather than as a separate step.
    Example usage:

    Instead of the normal 1 + N request save where N is the # of attachments:

        foo = Foo()
        foo.save()
        foo.put_attachment(
            name=filename,
            content=content,
            content_type=mime_type
        )

    You can use the following to do a single-request save:

        foo = Foo()

        attachment_builder = CouchAttachmentsBuilder(foo._attachments)
        attachment_builder.add(
            name=filename,
            content=content,
            content_type=mime_type
        )
        foo._attachments = attachment_builder.to_json()

        foo.save(encode_attachments=False)


        # or bulk save
        Foo.get_db().bulk_save([foo, ...])

    NB: If you save without encode_attachments=False
    (here or later on down the line)
    then your attachment content will end up base64 encoded!
    That's a real thing that's happened in the past,
    so be careful who you're passing this object on to!
    (Think signals, etc. where you have no control over who uses it next
    and how/whether they call .save() on the object.)

    """

    def __init__(self, original=None):
        self._dict = original or {}

    @staticmethod
    def couch_style_digest(data):
        return 'md5-{}'.format(base64.b64encode(hashlib.md5(data).digest()))

    def no_change(self, name, data):
        return (
            self._dict.get(name) and
            self._dict[name].get('digest') == self.couch_style_digest(data)
        )

    def add(self, content, name=None, content_type=None):
        if hasattr(content, 'read'):
            if hasattr(content, 'seek'):
                content.seek(0)
            data = content.read()
        else:
            data = content
        if isinstance(data, unicode):
            data = data.encode('utf-8')
        if content_type is None:
            content_type = ';'.join(filter(None, guess_type(name)))
        # optimization alert:
        # don't make couch re-save attachment if there's no change in content
        if self.no_change(name, data):
            # just set the content_type in case it's different
            # don't know of any case where this matters
            # but seems semantically correct
            self._dict[name].update({
                'content_type': content_type,
            })
        else:
            self._dict[name] = {
                'data': base64.b64encode(data),
                'content_type': content_type,
            }

    def remove(self, name):
        """
        raises a `KeyError` if there's no attachment called `name`
        """
        del self._dict[name]

    def to_json(self):
        return copy(self._dict)


class PaginateViewLogHandler(object):

    def log(self, message):
        # subclasses can override this to actually log something
        # built in implementation swallows it
        pass

    def view_starting(self, db, view_name, kwargs, total_emitted):
        self.log(u'Fetching rows {}-{} from couch'.format(
            total_emitted,
            total_emitted + kwargs['limit'] - 1)
        )
        startkey = kwargs.get('startkey')
        self.log(u'  startkey={!r}, startkey_docid={!r}'.format(startkey, kwargs.get('startkey_docid')))

    def view_ending(self, db, view_name, kwargs, total_emitted, time):
        self.log('View call took {}'.format(time))


def paginate_view(db, view_name, chunk_size,
                  log_handler=PaginateViewLogHandler(), **view_kwargs):
    """
    intended as a more performant drop-in replacement for

        iter(db.view(view_name, **kwargs))

    intended specifically to be more performant when dealing with
    large numbers of rows

    Note: If the contents of the couch view do not change over the duration of
    the paginate_view call, this is guaranteed to have the same results
    as a direct view call. If the view is updated, however,
    paginate_views may skip docs that were added/updated during this period
    or may include docs that were removed/updated during this period.
    For this reason, it's best to use this with views that update infrequently
    or that are sorted by date modified and/or add-only,
    or when exactness is not a strict requirement

    chunk_size is how many docs to fetch per request to couchdb

    """
    if view_kwargs.get('reduce', True):
        raise ValueError('paginate_view must be called with reduce=False')

    if 'limit' in view_kwargs:
        raise ValueError('paginate_view cannot be called with limit')

    if 'skip' in view_kwargs:
        raise ValueError('paginate_view cannot be called with skip')

    view_kwargs['limit'] = chunk_size
    total_emitted = 0
    len_results = -1
    while len_results:
        log_handler.view_starting(db, view_name, view_kwargs, total_emitted)
        start_time = datetime.datetime.utcnow()
        results = db.view(view_name, **view_kwargs)
        len_results = len(results)

        for result in results:
            yield result

        total_emitted += len_results
        log_handler.view_ending(db, view_name, view_kwargs, total_emitted,
                                datetime.datetime.utcnow() - start_time)
        if len_results:
            view_kwargs['startkey'] = result['key']
            view_kwargs['startkey_docid'] = result['id']
            view_kwargs['skip'] = 1


class ResumableDocsByTypeIterator(object):
    """Perform one-time resumable iteration over documents by type

    Iteration can be efficiently stopped and resumed. The iteration may
    omit documents that are added after the iteration begins or resumes
    and may include deleted documents.

    :param db: Couchdb database.
    :param doc_types: A list of doc type names to iterate on.
    :param iteration_key: A unique key identifying the iteration. This
    key will be used in combination with `doc_types` to maintain state
    about an iteration that is in progress. The state will be maintained
    indefinitely unless it is removed with `discard_state()`.
    :param chunk_size: Number of documents to yield before updating the
    iteration checkpoint. In the worst case about this many documents
    that were previously yielded may be yielded again if the iteration
    is stopped and later resumed.
    """

    def __init__(self, db, doc_types, iteration_key, chunk_size=100):
        if isinstance(doc_types, str):
            raise TypeError("expected list of strings, got %r" % (doc_types,))
        self.db = db
        self.original_doc_types = doc_types = sorted(doc_types)
        self.iteration_key = iteration_key
        self.chunk_size = chunk_size
        iteration_name = "{}/{}".format(iteration_key, " ".join(doc_types))
        self.iteration_id = hashlib.sha1(iteration_name).hexdigest()
        try:
            self.state = db.get(self.iteration_id)
        except ResourceNotFound:
            # new iteration
            self.state = {
                "_id": self.iteration_id,
                "doc_type": "ResumableDocsByTypeIteratorState",
                "retry": {},

                # for humans
                "name": iteration_name,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            args = {}
        else:
            # resume iteration
            args = self.state.get("offset", {}).copy()
            if args:
                assert args.get("startkey"), args
                doc_type = args["startkey"][0]
                # skip doc types before offset
                doc_types = doc_types[doc_types.index(doc_type):]
            else:
                # non-retry phase of iteration is complete
                doc_types = []
        args.update(
            view_name='all_docs/by_doc_type',
            chunk_size=chunk_size,
            log_handler=ResumableDocsByTypeLogHandler(self),
            include_docs=True,
            reduce=False,
        )
        self.view_args = args
        self.doc_types = doc_types

    def __iter__(self):
        args = self.view_args
        for doc_type in self.doc_types:
            if args.get("startkey", [None])[0] != doc_type:
                args.pop("startkey_docid", None)
                args["startkey"] = [doc_type]
            args["endkey"] = [doc_type, {}]
            for result in paginate_view(self.db, **args):
                yield result['doc']

        retried = {}
        while self.state["retry"] != retried:
            for doc_id, retries in list(self.state["retry"].iteritems()):
                if retries == retried.get(doc_id):
                    continue  # skip already retried (successfully)
                retried[doc_id] = retries
                try:
                    yield self.db.get(doc_id)
                except ResourceNotFound:
                    pass

        # save iteration state without offset to signal completion
        self.state.pop("offset", None)
        self.state["retry"] = {}
        self._save_state()

    def retry(self, doc, max_retry=3):
        """Add document to be yielded at end of iteration

        Iteration order of retry documents is undefined. All retry
        documents will be yielded after the initial non-retry phase of
        iteration has completed, and every retry document will be
        yielded each time the iterator is stopped and resumed during the
        retry phase. This method is relatively inefficient because it
        forces the iteration state to be saved to couch. If you find
        yourself calling this for many documents during the iteration
        you may want to consider a different retry strategy.

        :param doc: The doc dict to retry. It will be re-fetched from
        the database before being yielded from the iteration.
        :param max_retry: Maximum number of times a given document may
        be retried.
        :raises: `TooManyRetries` if this method has been called too
        many times with a given document.
        """
        doc_id = doc["_id"]
        retries = self.state["retry"].get(doc_id, 0) + 1
        if retries > max_retry:
            raise TooManyRetries(doc_id)
        self.state["retry"][doc_id] = retries
        self._save_state()

    def _save_state(self):
        self.state["timestamp"] = datetime.datetime.utcnow().isoformat()
        self.db.save_doc(self.state)

    def discard_state(self):
        try:
            self.db.delete_doc(self.iteration_id)
        except ResourceNotFound:
            pass
        self.__init__(
            self.db,
            self.original_doc_types,
            self.iteration_key,
            self.chunk_size,
        )


class ResumableDocsByTypeLogHandler(PaginateViewLogHandler):

    def __init__(self, iterator):
        self.iterator = iterator

    def view_starting(self, db, view_name, kwargs, total_emitted):
        offset = {k: v for k, v in kwargs.items() if k.startswith("startkey")}
        self.iterator.state["offset"] = offset
        self.iterator._save_state()


class TooManyRetries(Exception):
    pass


_override_db = threading.local()


class OverrideDB(object):

    def __init__(self, document_class, database):
        self.document_class = document_class
        self.database = database
        self.orig_database = None
        self.orig_get_db = None
        if not hasattr(_override_db, 'class_to_db'):
            _override_db.class_to_db = {}

    def __enter__(self):
        try:
            self.orig_database = _override_db.class_to_db[self.document_class]
        except KeyError:
            self.orig_get_db = self.document_class.get_db
            self.document_class.get_db = classmethod(_get_db)
        _override_db.class_to_db[self.document_class] = self.database

    def __exit__(self, exc_type, exc_val, exc_tb):
        # explict comparison with None necessary
        # because Database.__nonzero__ returns the doc count
        if self.orig_database is not None:
            _override_db.class_to_db[self.document_class] = self.orig_database
        else:
            assert self.orig_get_db
            del _override_db.class_to_db[self.document_class]
            self.document_class.get_db = self.orig_get_db


def _get_db(cls):
    return _override_db.class_to_db[cls]
