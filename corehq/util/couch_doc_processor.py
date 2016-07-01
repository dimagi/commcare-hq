import hashlib
from abc import abstractmethod, ABCMeta, abstractproperty
from datetime import datetime

import six
from couchdbkit import ResourceNotFound

from corehq.util.couch_helpers import PaginateViewLogHandler, paginate_view


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
                "timestamp": datetime.utcnow().isoformat()
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

    @property
    def progress_info(self):
        """Extra progress information

        This property can be used to store and retrieve extra progress
        information associated with the iteration. The information is
        persisted with the iteration state in couch.
        """
        return self.state.get("progress_info")

    @progress_info.setter
    def progress_info(self, info):
        self.state["progress_info"] = info
        self._save_state()

    def _save_state(self):
        self.state["timestamp"] = datetime.utcnow().isoformat()
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


class BulkProcessingFailed(Exception):
    pass


DOCS_SKIPPED_WARNING = """
        WARNING {} documents were not processed due to concurrent modification
        during migration. Run the migration again until you do not see this
        message.
        """


class BaseDocProcessor(six.with_metaclass(ABCMeta)):

    def __init__(self, slug):
        self.slug = slug

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractproperty
    def unique_key(self):
        return self.slug

    @abstractmethod
    def process_doc(self, doc, couchdb):
        """Process a single document

        :param doc: The document dict to be processed.
        :param couchdb: Couchdb database associated with the docs.
        :returns: True if doc was processed successfully else False. If this returns False
        the document migration will be retried later.
        """
        raise NotImplementedError

    def process_bulk_docs(self, docs, couchdb):
        """Process a batch of documents. The default implementation passes
        each doc in turn to ``process_doc``.

        :param docs: A list of document dicts to be processed.
        :param couchdb: Couchdb database associated with the docs.
        :returns: True if doc was processed successfully else False.
        If this returns False the processing will be halted.
        """
        return all(self.process_doc(doc, couchdb) for doc in docs)

    def handle_skip(self, doc):
        """Called when a document is going to be skipped i.e. it has been
        retried > max_retries.

        :returns: True to indicate that the skip has been handled
                  or False to stop execution
        """
        return False

    def processing_complete(self, skipped):
        pass

    def should_process(self, doc):
        """
        :param doc: the document to filter
        :return: True if this doc should be migrated
        """
        return True


class CouchDocumentProcessor(object):
    """Process Couch Docs

    :param doc_type_map: Dict of `doc_type_name: model_class` pairs.
    :param doc_processor: A `BaseDocProcessor` object used to
    process documents.
    :param reset: Reset existing processor state (if any), causing all
    documents to be reconsidered for processing, if this is true.
    :param max_retry: Number of times to retry processing a document
    before giving up.
    :param chunk_size: Maximum number of records to read from couch at
    one time. It may be necessary to use a smaller chunk size if the
    records being processed are very large and the default chunk size of
    100 would exceed available memory.
    """
    def __init__(self, doc_type_map, doc_processor, reset=False, max_retry=2, chunk_size=100):
        self.doc_type_map = doc_type_map
        self.doc_processor = doc_processor
        self.reset = reset
        self.max_retry = max_retry
        self.chunk_size = chunk_size

        self.couchdb = next(iter(doc_type_map.values())).get_db()
        assert all(m.get_db() is self.couchdb for m in doc_type_map.values()), \
            "documents must live in same couch db: %s" % repr(doc_type_map)

        self.docs_by_type = ResumableDocsByTypeIterator(
            self.couchdb, doc_type_map, doc_processor.unique_key, chunk_size=chunk_size
        )

        self.visited = 0
        self.previously_visited = 0
        self.total = 0

        self.processed = 0
        self.skipped = 0

        self.start = None

    def has_started(self):
        return bool(self.docs_by_type.progress_info)

    @property
    def session_visited(self):
        return self.visited - self.previously_visited

    @property
    def session_total(self):
        return self.total - self.previously_visited

    @property
    def attempted(self):
        return self.processed + self.skipped

    @property
    def timing(self):
        """Returns a tuple of (elapsed, remaining)"""
        elapsed = datetime.now() - self.start
        if self.session_visited > self.session_total:
            remaining = "?"
        else:
            session_remaining = self.session_total - self.session_visited
            remaining = elapsed / self.session_visited * session_remaining
        return elapsed, remaining

    def _setup(self):
        from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type

        self.total = sum(get_doc_count_by_type(self.couchdb, doc_type)
                    for doc_type in self.doc_type_map)

        if self.reset:
            self.docs_by_type.discard_state()
        elif self.docs_by_type.progress_info:
            info = self.docs_by_type.progress_info
            old_total = info["total"]
            # Estimate already visited based on difference of old/new
            # totals. The theory is that new or deleted records will be
            # evenly distributed across the entire set.
            self.visited = int(round(float(self.total) / old_total * info["visited"]))
            self.previously_visited = self.visited
        print("Processing {} documents{}: {}...".format(
            self.total,
            " (~{} already processed)".format(self.visited) if self.visited else "",
            ", ".join(sorted(self.doc_type_map))
        ))

        self.start = datetime.now()

    def run(self):
        """
        :returns: A tuple `(<num processed>, <num skipped>)`
        """
        self._setup()
        with self.doc_processor:
            for doc in self.docs_by_type:
                self._process_doc(doc)
                self._update_progress()

        self._processing_complete()

        return self.processed, self.skipped

    def _process_doc(self, doc):
        if not self.doc_processor.should_process(doc):
            return

        ok = self.doc_processor.process_doc(doc, self.couchdb)
        if ok:
            self.processed += 1
        else:
            try:
                self.docs_by_type.retry(doc, self.max_retry)
            except TooManyRetries:
                if not self.doc_processor.handle_skip(doc):
                    raise
                else:
                    print("Skip: {doc_type} {_id}".format(**doc))
                    self.skipped += 1

    def _update_progress(self):
        self.visited += 1
        if self.visited % self.chunk_size == 0:
            self.docs_by_type.progress_info = {"visited": self.visited, "total": self.total}

        if self.attempted % self.chunk_size == 0:
            elapsed, remaining = self.timing
            print("Processed {}/{} of {} documents in {} ({} remaining)"
                  .format(self.processed, self.visited, self.total, elapsed, remaining))

    def _processing_complete(self):
        if self.session_visited:
            self.docs_by_type.progress_info = {"visited": self.visited, "total": self.total}
        self.doc_processor.processing_complete(self.skipped)
        print("Processed {}/{} of {} documents ({} previously processed, {} filtered out).".format(
            self.processed,
            self.visited,
            self.total,
            self.previously_visited,
            self.session_visited - self.attempted
        ))
        if self.skipped:
            print(DOCS_SKIPPED_WARNING.format(self.skipped))


class BulkDocProcessor(CouchDocumentProcessor):
    """Process couch docs in batches

    The bulk doc processor will send a batch of documents to the document
    processor. If the processor does not respond with True then
    the iteration is halted. Restarting the iteration will start by
    re-sending the previous chunk to the processor

    :param doc_type_map: Dict of `doc_type_name: model_class` pairs.
    :param doc_processor: A `BaseDocProcessor` object used to
    process documents.
    :param reset: Reset existing processor state (if any), causing all
    documents to be reconsidered for processing, if this is true.
    :param chunk_size: Maximum number of records to read from couch at
    one time. It may be necessary to use a smaller chunk size if the
    records being processed are very large and the default chunk size of
    100 would exceed available memory.
    """
    def __init__(self, doc_type_map, doc_processor, reset=False, chunk_size=100):
        super(BulkDocProcessor, self).__init__(doc_type_map, doc_processor, reset=reset, chunk_size=chunk_size)
        self.changes = []

    def _process_doc(self, doc):
        if self.doc_processor.should_process(doc):
            self.changes.append(doc)

        if len(self.changes) % self.chunk_size == 0:
            self._process_chunk()

    def _process_chunk(self):
        ok = self.doc_processor.process_bulk_docs(self.changes, self.couchdb)
        if ok:
            self.processed += len(self.changes)
            self.changes = []
        else:
            raise BulkProcessingFailed("Processing batch failed")

    def _update_progress(self):
        self.visited += 1
        if self.visited % self.chunk_size == 0:
            self.docs_by_type.progress_info = {"visited": self.visited, "total": self.total}

            elapsed, remaining = self.timing
            print("Processed {}/{} of {} documents in {} ({} remaining)"
                  .format(self.processed, self.visited, self.total, elapsed, remaining))

    def _processing_complete(self):
        if len(self.changes):
            self._process_chunk()

        super(BulkDocProcessor, self)._processing_complete()
