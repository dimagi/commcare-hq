from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import weakref
from abc import ABCMeta, abstractmethod

import six

from .progress import ProgressManager, ProcessorProgressLogger
from ..pagination import PaginationEventHandler, TooManyRetries


class BulkProcessingFailed(Exception):
    pass


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
        self.document_provider = document_provider

        self.document_iterator = self.document_provider.get_document_iterator(chunk_size, event_handler)
        self.progress = ProgressManager(
            self.document_iterator,
            reset=reset,
            chunk_size=chunk_size,
            logger=progress_logger or ProcessorProgressLogger(),
        )

    def has_started(self):
        return bool(self.document_iterator.get_iterator_detail('progress'))

    def run(self):
        """
        :returns: A tuple `(<num processed>, <num skipped>)`
        """
        self.progress.total = self.document_provider.get_total_document_count()

        with self.doc_processor, self.progress:
            for doc in self.document_iterator:
                self._process_doc(doc)

        self.doc_processor.processing_complete(self.progress.skipped)

        return self.progress.processed, self.progress.skipped

    def _process_doc(self, doc):
        if not self.doc_processor.should_process(doc):
            return

        ok = self.doc_processor.process_doc(doc)
        if ok:
            self.progress.add()
        else:
            try:
                self.document_iterator.retry(doc['_id'], self.max_retry)
            except TooManyRetries:
                if not self.doc_processor.handle_skip(doc):
                    raise
                else:
                    self.progress.skip(doc)


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
            self.progress.add(len(self.changes))
            self.changes = []
        else:
            raise BulkProcessingFailed("Processing batch failed")
