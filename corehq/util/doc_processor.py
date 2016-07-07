import weakref
from abc import ABCMeta, abstractmethod
from datetime import datetime

import six
from couchdbkit import ResourceNotFound

from corehq.util.couch_helpers import PaginatedViewArgsProvider
from corehq.util.pagination import PaginationEventHandler, ResumableFunctionIterator, TooManyRetries


class ResumableDocsByTypeArgsProvider(PaginatedViewArgsProvider):
    def __init__(self, initial_view_kwargs, doc_types):
        super(ResumableDocsByTypeArgsProvider, self).__init__(initial_view_kwargs)
        self.doc_types = doc_types

    def get_next_args(self, result, *last_args, **last_view_kwargs):
        try:
            return super(ResumableDocsByTypeArgsProvider, self).get_next_args(result, *last_args, **last_view_kwargs)
        except StopIteration:
            last_doc_type = last_view_kwargs["startkey"][0]
            # skip doc types already processed
            index = self.doc_types.index(last_doc_type) + 1
            self.doc_types = self.doc_types[index:]
            try:
                next_doc_type = self.doc_types[0]
            except IndexError:
                raise StopIteration
            last_view_kwargs.pop('skip', None)
            last_view_kwargs.pop("startkey_docid", None)
            last_view_kwargs['startkey'] = [next_doc_type]
            last_view_kwargs['endkey'] = [next_doc_type, {}]
        return last_args, last_view_kwargs


def ResumableDocsByTypeIterator(db, doc_types, iteration_key, chunk_size=100, view_event_handler=None):
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

    def data_function(**view_kwargs):
        return db.view('all_docs/by_doc_type', **view_kwargs)

    doc_types = sorted(doc_types)
    data_function.__name__ = " ".join(doc_types)

    view_kwargs = {
        'limit': chunk_size,
        'include_docs': True,
        'reduce': False,
        'startkey': [doc_types[0]],
        'endkey': [doc_types[0], {}]
    }

    args_provider = ResumableDocsByTypeArgsProvider(view_kwargs, doc_types)

    class ResumableDocsIterator(ResumableFunctionIterator):
        def __iter__(self):
            for result in super(ResumableDocsIterator, self).__iter__():
                yield result['doc']

    def item_getter(doc_id):
        try:
            return {'doc': db.get(doc_id)}
        except ResourceNotFound:
            pass

    return ResumableDocsIterator(iteration_key, data_function, args_provider, item_getter, view_event_handler)


class BulkProcessingFailed(Exception):
    pass


DOCS_SKIPPED_WARNING = """
        WARNING {} documents were not processed due to concurrent modification
        during migration. Run the migration again until you do not see this
        message.
        """


class BaseDocProcessor(six.with_metaclass(ABCMeta)):

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def process_doc(self, doc):
        """Process a single document

        :param doc: The document dict to be processed.
        :returns: True if doc was processed successfully else False. If this returns False
        the document migration will be retried later.
        """
        raise NotImplementedError

    def process_bulk_docs(self, docs):
        """Process a batch of documents. The default implementation passes
        each doc in turn to ``process_doc``.

        :param docs: A list of document dicts to be processed.
        :returns: True if doc was processed successfully else False.
        If this returns False the processing will be halted.
        """
        return all(self.process_doc(doc) for doc in docs)

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


class ProcessorProgressLogger(object):
    def progress_starting(self, total, previously_visited):
        print("Processing {} documents{}: ...".format(
            total,
            " (~{} already processed)".format(previously_visited) if previously_visited else ""
        ))

    def document_skipped(self, doc_dict):
        print("Skip: {doc_type} {_id}".format(**doc_dict))

    def progress(self, total, processed, visited, time_elapsed, time_remaining):
        print("Processed {}/{} of {} documents in {} ({} remaining)"
              .format(processed, visited, total, time_elapsed, time_remaining))

    def progress_complete(self, total, processed, visited, previously_visited, filtered):
        print("Processed {}/{} of {} documents ({} previously processed, {} filtered out).".format(
            processed,
            visited,
            total,
            previously_visited,
            filtered
        ))


class CouchProcessorProgressLogger(ProcessorProgressLogger):
    """
    :param doc_type_map: Dict of `doc_type_name: model_class` pairs.
    """
    def __init__(self, doc_type_map):
        self.doc_type_map = doc_type_map

    def progress_starting(self, total, previously_visited):
        print("Processing {} documents{}: {}...".format(
            total,
            " (~{} already processed)".format(previously_visited) if previously_visited else "",
            ", ".join(sorted(self.doc_type_map))
        ))


class DocumentProvider(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_document_iterator(self, chunk_size, event_handler=None):
        """
        :param chunk_size: Maximum number of records to read from the database at one time
        :param event_handler: instance of ``PaginateViewLogHandler`` to be notified of view events.
        :return: an instance of ``ResumableFunctionIterator``
        """
        raise NotImplementedError

    @abstractmethod
    def get_total_document_count(self):
        """
        :return: the total count of documents expected
        """
        raise NotImplementedError


class CouchDocumentProvider(DocumentProvider):
    """Document provider for couch documents.

    All documents must live in the same couch database.

    :param iteration_key: unique key to identify the document iterator
    :param doc_type_map: Dict of `doc_type_name: model_class` pairs.
    """
    def __init__(self, iteration_key, doc_type_map):
        self.iteration_key = iteration_key
        self.doc_type_map = doc_type_map

        self.couchdb = next(iter(doc_type_map.values())).get_db()
        assert all(m.get_db() is self.couchdb for m in doc_type_map.values()), \
            "documents must live in same couch db: %s" % repr(doc_type_map)

    def get_document_iterator(self, chunk_size, event_handler=None):
        return ResumableDocsByTypeIterator(
            self.couchdb, self.doc_type_map, self.iteration_key,
            chunk_size=chunk_size, view_event_handler=event_handler
        )

    def get_total_document_count(self):
        from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type
        return sum(
            get_doc_count_by_type(self.couchdb, doc_type)
            for doc_type in self.doc_type_map
        )


class DocumentProcessor(object):
    """Process Docs

    :param document_provider: A ``DocumentProvider`` object
    :param doc_processor: A ``BaseDocProcessor`` object used to process documents.
    :param reset: Reset existing processor state (if any), causing all
    documents to be reconsidered for processing, if this is true.
    :param max_retry: Number of times to retry processing a document before giving up.
    :param chunk_size: Maximum number of records to read from couch at
    one time. It may be necessary to use a smaller chunk size if the
    records being processed are very large and the default chunk size of
    100 would exceed available memory.
    :param event_handler: A ``PaginateViewLogHandler`` object to be notified of pagination events.
    :param progress_logger: A ``ProcessorProgressLogger`` object to notify of progress events.
    """
    def __init__(self, document_provider, doc_processor, reset=False, max_retry=2,
                 chunk_size=100, event_handler=None, progress_logger=None):
        self.doc_processor = doc_processor
        self.reset = reset
        self.max_retry = max_retry
        self.chunk_size = chunk_size
        self.progress_logger = progress_logger or ProcessorProgressLogger()

        self.document_provider = document_provider

        self.document_iterator = self.document_provider.get_document_iterator(chunk_size, event_handler)

        self.visited = 0
        self.previously_visited = 0
        self.total = 0

        self.processed = 0
        self.skipped = 0

        self.start = None

    def has_started(self):
        return bool(self.document_iterator.progress_info)

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
        self.total = self.document_provider.get_total_document_count()

        if self.reset:
            self.document_iterator.discard_state()
        elif self.document_iterator.progress_info:
            info = self.document_iterator.progress_info
            old_total = info["total"]
            # Estimate already visited based on difference of old/new
            # totals. The theory is that new or deleted records will be
            # evenly distributed across the entire set.
            self.visited = int(round(float(self.total) / old_total * info["visited"]))
            self.previously_visited = self.visited
        self.progress_logger.progress_starting(self.total, self.previously_visited)

        self.start = datetime.now()

    def run(self):
        """
        :returns: A tuple `(<num processed>, <num skipped>)`
        """
        self._setup()
        with self.doc_processor:
            for doc in self.document_iterator:
                self._process_doc(doc)
                self._update_progress()

        self._processing_complete()

        return self.processed, self.skipped

    def _process_doc(self, doc):
        if not self.doc_processor.should_process(doc):
            return

        ok = self.doc_processor.process_doc(doc)
        if ok:
            self.processed += 1
        else:
            try:
                self.document_iterator.retry(doc['_id'], self.max_retry)
            except TooManyRetries:
                if not self.doc_processor.handle_skip(doc):
                    raise
                else:
                    self.progress_logger.document_skipped(doc)
                    self.skipped += 1

    def _update_progress(self):
        self.visited += 1
        if self.visited % self.chunk_size == 0:
            self.document_iterator.progress_info = {"visited": self.visited, "total": self.total}

        if self.attempted % self.chunk_size == 0:
            elapsed, remaining = self.timing
            self.progress_logger.progress(
                self.processed, self.visited, self.total, elapsed, remaining
            )

    def _processing_complete(self):
        if self.session_visited:
            self.document_iterator.progress_info = {"visited": self.visited, "total": self.total}
        self.doc_processor.processing_complete(self.skipped)
        self.progress_logger.progress_complete(
            self.processed,
            self.visited,
            self.total,
            self.previously_visited,
            self.session_visited - self.attempted
        )
        if self.skipped:
            print(DOCS_SKIPPED_WARNING.format(self.skipped))


class BulkDocProcessorEventHandler(PaginationEventHandler):

    def __init__(self, processor):
        self.processor_ref = weakref.ref(processor)

    def page_end(self, total_emitted, duration, *args, **kwargs):
        processor = self.processor_ref()
        if processor:
            processor.process_chunk()
        else:
            raise BulkProcessingFailed("Processor has gone away")


class BulkDocProcessor(DocumentProcessor):
    """Process docs in batches

    The bulk doc processor will send a batch of documents to the document
    processor. If the processor does not respond with True then
    the iteration is halted. Restarting the iteration will start by
    re-sending the previous chunk to the processor.

    The size of the batches passed to the document processor may vary
    depending on how they are being filtered by the
    document processor but will never exceed ``chunk_size``.

    :param document_provider: A ``DocumentProvider`` object
    :param doc_processor: A ``BaseDocProcessor`` object used to process documents.
    :param reset: Reset existing processor state (if any), causing all
    documents to be reconsidered for processing, if this is true.
    :param max_retry: Number of times to retry processing a document before giving up.
    :param chunk_size: Maximum number of records to read from couch at
    one time. It may be necessary to use a smaller chunk size if the
    records being processed are very large and the default chunk size of
    100 would exceed available memory.
    :param progress_logger: A ``ProcessorProgressLogger`` object to notify of progress events.
    """
    def __init__(self, document_provider, doc_processor, reset=False, max_retry=2,
                 chunk_size=100, progress_logger=None):

        event_handler = BulkDocProcessorEventHandler(self)
        super(BulkDocProcessor, self).__init__(
            document_provider, doc_processor, reset, max_retry, chunk_size,
            event_handler, progress_logger
        )
        self.changes = []

    def _process_doc(self, doc):
        if self.doc_processor.should_process(doc):
            self.changes.append(doc)

    def process_chunk(self):
        """Called by the BulkDocProcessorLogHandler"""
        ok = self.doc_processor.process_bulk_docs(self.changes)
        if ok:
            self.processed += len(self.changes)
            self.changes = []
        else:
            raise BulkProcessingFailed("Processing batch failed")

    def _update_progress(self):
        self.visited += 1
        if self.visited % self.chunk_size == 0:
            self.document_iterator.progress_info = {"visited": self.visited, "total": self.total}

            elapsed, remaining = self.timing
            self.progress_logger.progress(
                self.total, self.processed, self.visited, elapsed, remaining
            )
