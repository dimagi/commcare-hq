from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from datetime import datetime, timedelta

import attr

DOCS_SKIPPED_WARNING = """
        WARNING {} documents were not processed due to concurrent modification
        during migration. Run the migration again until you do not see this
        message.
        """

MIN_PROGRESS_INTERVAL = timedelta(minutes=5)


@attr.s
class ProgressManager(object):
    """Manage document processing progress and estimate time remaining

    :param iterable: Instance of ``ResumableFunctionIterator`` (used to
    get and save state for resumable migrations).
    :param total: Total number of documents in iterable (may
    be estimated).
    :param reset: Discard existing iteration state (if any) if true.
    :param chunk_size: Number of items to process before updating progress.
    :param logger: Object used for logging progress.
    See ``ProcessorProgressLogger`` for interface.
    """

    iterable = attr.ib()
    total = attr.ib(default=0)
    reset = attr.ib(default=False)
    chunk_size = attr.ib(default=100)
    logger = attr.ib(factory=lambda: ProcessorProgressLogger())

    visited = attr.ib(init=False, default=0)
    previously_visited = attr.ib(init=False, default=0)
    processed = attr.ib(init=False, default=0)
    skipped = attr.ib(init=False, default=0)
    start = attr.ib(init=False, default=None)

    @property
    def _session_total(self):
        return self.total - self.previously_visited

    @property
    def timing(self):
        """Returns a tuple of (elapsed, remaining)"""
        elapsed = datetime.now() - self.start
        if self.processed >= self._session_total or not self.processed:
            remaining = "?"
        else:
            session_remaining = self._session_total - self.processed
            remaining = elapsed // self.processed * session_remaining
        return elapsed, remaining

    def __enter__(self):
        self.start = datetime.now()
        if self.reset:
            self.iterable.discard_state()
        elif self.iterable.get_iterator_detail('progress'):
            info = self.iterable.get_iterator_detail('progress')
            old_total = info["total"]
            # Estimate already visited based on difference of old/new
            # totals. The theory is that new or deleted records will be
            # evenly distributed across the entire set.
            self.visited = int(float(self.total) / old_total * info["visited"] + 0.5) if old_total else 0
            self.previously_visited = self.visited
        self.logger.progress_starting(self.total, self.previously_visited)

    def add(self, num=1):
        """Increment progress by one

        Call for each item after it is successfully processed.
        """
        self.processed += num
        self._update(num)

    def skip(self, doc):
        """Record skipped item

        Call for each item that cannot be processed.
        """
        self.logger.document_skipped(doc)
        self.skipped += 1
        self._update()

    @property
    def _state(self):
        return {"visited": self.visited, "total": self.total}

    def _update(self, num=1):
        self.visited += num
        if self.visited > self.total:
            self.total = self.visited

        now = datetime.now()
        attempted = self.processed + self.skipped
        last_attempted = getattr(self, "_last_attempted", None)
        if ((attempted % self.chunk_size == 0 and attempted != last_attempted)
                or now >= getattr(self, "_next_progress_update", now)):
            self.iterable.set_iterator_detail('progress', self._state)
            elapsed, remaining = self.timing
            self.logger.progress(
                self.processed, self.visited, self.total, elapsed, remaining
            )
            self._last_attempted = attempted
            self._next_progress_update = now + MIN_PROGRESS_INTERVAL

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            if self.processed:
                self.iterable.set_iterator_detail('progress', self._state)
            self.logger.progress_complete(
                self.processed,
                self.visited,
                self.total,
                self.previously_visited,
            )
            if self.skipped:
                print(DOCS_SKIPPED_WARNING.format(self.skipped))


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

    def progress_complete(self, processed, visited, total, previously_visited):
        print("Processed {}/{} of {} documents ({} previously processed).".format(
            processed,
            visited,
            total,
            previously_visited,
        ))
