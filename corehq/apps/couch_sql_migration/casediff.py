from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict

import gevent
from gevent.pool import Pool
from itertools import count

from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from dimagi.utils.chunked import chunked

log = logging.getLogger(__name__)


class CaseDiffQueue(object):
    """A queue that diffs cases when all relevant forms have been processed

    Cases and other internal state of this queue are persisted in the
    state db so they will be preserved between invocations when the
    queue is used as a context manager. Some cases may be diffed more
    than once, but none should be lost on account of of stop/resume.
    """

    BATCH_SIZE = 100

    def __init__(self, statedb, diff_cases):
        self.statedb = statedb
        self.diff_cases = diff_cases
        self.processed_forms = defaultdict(set)  # case id -> processed form ids
        self.cases_to_diff = {}  # case id -> case doc (JSON)
        self.pool = Pool(5)
        self.case_batcher = BatchProcessor(self.pool)

    def __enter__(self):
        self._load_resume_state()
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        try:
            if exc_type is None:
                self._process_remaining_diffs()
        finally:
            self._save_resume_state()

    def update(self, case_ids, form_id):
        """Update the case diff queue with case ids touched by form

        :param case_ids: set of case ids.
        :param form_id: form id touching case ids.
        """
        log.debug("update: cases=%s form=%s", case_ids, form_id)
        processed = self.processed_forms
        for case_id in case_ids:
            processed[case_id].add(form_id)
            if len(processed) >= self.BATCH_SIZE:
                self._enqueue_pending_cases(processed)
                processed = self.processed_forms = defaultdict(set)
        task_switch()

    def _enqueue_pending_cases(self, processed):
        self.case_batcher.spawn(self._enqueue_cases, list(processed))

    def _enqueue_cases(self, case_ids):
        for case in CaseAccessorCouch.get_cases(case_ids):
            self.enqueue(case.to_json())

    def enqueue(self, case_doc):
        case_id = case_doc["_id"]
        self.cases_to_diff[case_id] = case_doc
        if len(self.cases_to_diff) >= self.BATCH_SIZE:
            self._diff_cases()

    def _diff_cases(self):
        self.case_batcher.spawn(self.diff_cases, self.cases_to_diff)
        self.cases_to_diff = {}

    def _process_remaining_diffs(self):
        log.debug("process remaining diffs")
        if self.processed_forms:
            self._enqueue_pending_cases(self.processed_forms)
        pool = self.pool
        while self.cases_to_diff or pool:
            if self.cases_to_diff:
                self._diff_cases()
            while not pool.join(timeout=10):
                log.info('Waiting on {} case diff workers'.format(len(pool)))
        self.pool = None
        self.processed_forms = None

    def _save_resume_state(self):
        state = {}
        if self.processed_forms:
            state["processed"] = dict_of_lists(self.processed_forms)
        if self.case_batcher or self.cases_to_diff:
            state["to_diff"] = list(iter_unprocessed(self.case_batcher))
            state["to_diff"].extend(self.cases_to_diff)
        log.debug("resume state: %s", state)
        self.statedb.set_resume_state(type(self).__name__, state)

    def _load_resume_state(self):
        state = self.statedb.pop_resume_state(type(self).__name__, {})
        if "to_diff" in state:
            for chunk in chunked(state["to_diff"], self.BATCH_SIZE, list):
                self._enqueue_pending_cases(chunk)
        if "processed" in state:
            for key, value in state["processed"].items():
                self.processed_forms[key].update(value)


def task_switch():
    gevent.sleep()


def dict_of_lists(value):
    return {k: list(v) for k, v in value.items()}


def iter_unprocessed(batcher):
    return (item for batch in batcher for item in batch)


def get_case_form_ids(couch_case):
    """Get the set of form ids that touched the given couch case object"""
    form_ids = set(couch_case.xform_ids)
    for action in couch_case.actions:
        form_ids.add(action.xform_id)
    return form_ids


class BatchProcessor(object):
    """Process batches of items with a worker pool

    Each batch of items is retained until its processing job has
    completed successfully. Unprocessed batches can be retrieved
    by iterating on the processor object.
    """

    def __init__(self, pool):
        self.pool = pool
        self.batches = {}
        self.key_gen = count()

    def __repr__(self):
        return "<BatchProcessor {}>".format(self.batches)

    def spawn(self, process, batch):
        key = next(self.key_gen)
        self.batches[key] = batch
        self._process_batch(process, key)

    def _process_batch(self, process, key):
        def process_batch(key):
            log.debug("call %s key=%s", process.__name__, key)
            try:
                process(self.batches[key])
            except Exception as err:
                log.warn("batch processing error: %s: %s", type(err).__name__, err)
                raise
            else:
                self.batches.pop(key)

        log.debug("schedule %s key=%s", process.__name__, key)
        self.pool.spawn(process_batch, key)

    def __bool__(self):
        """Return true if there are unprocessed batches else false"""
        return bool(self.batches)

    __nonzero__ = __bool__

    def __iter__(self):
        return iter(self.batches.values())
