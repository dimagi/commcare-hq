from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict
from itertools import chain, count

import attr
import gevent
import six
from gevent.pool import Pool

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
        self.pending_cases = defaultdict(set)  # case id -> processed form ids
        self.cases_to_diff = {}  # case id -> case doc (JSON)
        self.pool = Pool(5)
        self.case_batcher = BatchProcessor(self.pool)
        self.diff_batcher = BatchProcessor(self.pool)

        # Core data structure: case id -> CaseRecord. Each CaseRecord
        # maintains a set of unprocessed form ids for each case known
        # to the migration. Forms are removed from the set as they are
        # processed. When the set of form ids for a given case becomes
        # empty it is queued to be diffed and the corresponding
        # CaseRecord is removed.
        self.cases = {}

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
        pending = self.pending_cases
        for case_id in case_ids:
            pending[case_id].add(form_id)
            if len(pending) >= self.BATCH_SIZE:
                self._add_pending_cases(pending)
                pending = self.pending_cases = defaultdict(set)
        task_switch()

    def _add_pending_cases(self, pending_cases):
        log.debug("add pending cases %s", pending_cases)
        self.case_batcher.spawn(self._load_cases, pending_cases)

    def _load_cases(self, pending):
        """Load cases and try to diff them as forms are processed

        :param pending: dict of processed form id sequences (list
        or set) by case id.
        """
        cases = self.cases
        case_ids = []
        for case_id, processed_form_ids in pending.items():
            if case_id in cases:
                # try to diff
                self._try_to_diff(cases[case_id], processed_form_ids)
            else:
                case_ids.append(case_id)
        for case in CaseAccessorCouch.get_cases(case_ids):
            form_ids = get_case_form_ids(case)
            rec = CaseRecord(case, form_ids)
            cases[case.case_id] = rec
            self._try_to_diff(rec, pending[case.case_id])

    def _try_to_diff(self, rec, processed_form_ids):
        log.debug("trying case %s forms %s - %s",
            rec.id, rec.remaining_forms, processed_form_ids)
        for form_id in processed_form_ids:
            rec.add_processed(form_id)
        if not rec.remaining_forms:
            self.enqueue(rec.case.to_json())

    def enqueue(self, case_doc):
        case_id = case_doc["_id"]
        self.cases.pop(case_id, None)
        self.cases_to_diff[case_id] = case_doc
        if len(self.cases_to_diff) >= self.BATCH_SIZE:
            self._diff_cases()

    def _diff_cases(self):
        self.diff_batcher.spawn(self.diff_cases, self.cases_to_diff)
        self.cases_to_diff = {}

    def _process_remaining_diffs(self):
        log.debug("process remaining diffs")
        if self.pending_cases:
            self._add_pending_cases(self.pending_cases)
            self.pending_cases = defaultdict(set)
        pool = self.pool
        while self.cases_to_diff or pool:
            if self.cases_to_diff:
                self._diff_cases()
            while not pool.join(timeout=10):
                log.info('Waiting on {} case diff workers'.format(len(pool)))
        self.pool = None

    def _save_resume_state(self):
        state = {}
        if self.pending_cases or self.case_batcher or self.cases:
            recs = ((r.id, list(r.processed_forms)) for r in self.cases.values())
            pending = defaultdict(list, recs)
            for batch in chain(self.case_batcher, [self.pending_cases]):
                for case_id, processed_forms in batch.items():
                    pending[case_id].extend(processed_forms)
            state["pending"] = dict(pending)
        if self.diff_batcher or self.cases_to_diff:
            state["to_diff"] = list(chain.from_iterable(self.diff_batcher))
            state["to_diff"].extend(self.cases_to_diff)
        log.debug("resume state: %s", state)
        self.statedb.set_resume_state(type(self).__name__, state)

    def _load_resume_state(self):
        state = self.statedb.pop_resume_state(type(self).__name__, {})
        if "to_diff" in state:
            for chunk in chunked(state["to_diff"], self.BATCH_SIZE, list):
                self.diff_batcher.spawn(self._enqueue_cases, chunk)
        if "pending" in state:
            for chunk in chunked(state["pending"].items(), self.BATCH_SIZE, list):
                self._add_pending_cases(dict(chunk))

    def _enqueue_cases(self, case_ids):
        for case in CaseAccessorCouch.get_cases(case_ids):
            self.enqueue(case.to_json())


def task_switch():
    gevent.sleep()


def get_case_form_ids(couch_case):
    """Get the set of form ids that touched the given couch case object"""
    form_ids = set(couch_case.xform_ids)
    for action in couch_case.actions:
        form_ids.add(action.xform_id)
    return form_ids


@attr.s(slots=True)
class CaseRecord(object):

    case = attr.ib()
    remaining_forms = attr.ib()
    processed_forms = attr.ib(factory=set, init=False)

    @property
    def id(self):
        return self.case.case_id

    def add_processed(self, form_id):
        self.remaining_forms.discard(form_id)
        self.processed_forms.add(form_id)


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
                log.warn("batch processing error: %s: %s",
                    type(err).__name__, err, exc_info=True)
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
