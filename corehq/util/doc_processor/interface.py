from __future__ import print_function
from __future__ import absolute_import
import weakref
from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta

import six

from corehq.util.pagination import PaginationEventHandler, TooManyRetries


class BulkProcessingFailed(Exception):
    pass


DOCS_SKIPPED_WARNING = """
        WARNING {} documents were not processed due to concurrent modification
        during migration. Run the migration again until you do not see this
        message.
        """

MIN_PROGRESS_INTERVAL = timedelta(minutes=5)


class BaseDocProcessor(six.with_metaclass(ABCMeta)):
    """Base class for processors that get passed"""

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

    def progress(self, processed, visited, total, time_elapsed, time_remaining):
        print("Processed {}/{} of {} documents in {} ({} remaining)"
              .format(processed, visited, total, time_elapsed, time_remaining))

    def progress_complete(self, processed, visited, total, previously_visited, filtered):
        print("Processed {}/{} of {} documents ({} previously processed, {} filtered out).".format(
            processed,
            visited,
            total,
            previously_visited,
            filtered
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


class DocumentProcessorController(object):
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
        return bool(self.document_iterator.get_iterator_detail('progress'))

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
        elif self.document_iterator.get_iterator_detail('progress'):
            info = self.document_iterator.get_iterator_detail('progress')
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
        if self.visited > self.total:
            self.total = self.visited
        if self.visited % self.chunk_size == 0:
            self.document_iterator.set_iterator_detail('progress',
                {"visited": self.visited, "total": self.total})

        now = datetime.now()
        attempted = self.attempted
        last_attempted = getattr(self, "_last_attempted", None)
        if ((attempted % self.chunk_size == 0 and attempted != last_attempted)
                or now >= getattr(self, "_next_progress_update", now)):
            elapsed, remaining = self.timing
            self.progress_logger.progress(
                self.processed, self.visited, self.total, elapsed, remaining
            )
            self._last_attempted = attempted
            self._next_progress_update = now + MIN_PROGRESS_INTERVAL

    def _processing_complete(self):
        if self.session_visited:
            self.document_iterator.set_iterator_detail('progress',
                {"visited": self.visited, "total": self.total})
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


class BulkDocProcessor(DocumentProcessorController):
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
            self.document_iterator.set_iterator_detail('progress', {"visited": self.visited, "total": self.total})

            elapsed, remaining = self.timing
            self.progress_logger.progress(
                self.processed, self.visited, self.total, elapsed, remaining
            )
