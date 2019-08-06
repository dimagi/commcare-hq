from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict
from itertools import chain, count

import gevent
import six
from gevent.pool import Pool
from gevent.event import Event

from casexml.apps.case.xform import get_case_ids_from_form
from casexml.apps.stock.models import StockReport
from corehq.apps.commtrack.models import StockState
from corehq.apps.tzmigration.timezonemigration import json_diff
from corehq.form_processor.backends.couch.dbaccessors import (
    CaseAccessorCouch,
    FormAccessorCouch,
)
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    LedgerAccessorSQL,
)
from corehq.form_processor.exceptions import MissingFormXml
from dimagi.utils.chunked import chunked

from .diff import filter_case_diffs, filter_ledger_diffs

log = logging.getLogger(__name__)

STATUS_INTERVAL = 300  # 5 minutes


class CaseDiffQueue(object):
    """A queue that diffs cases when all relevant forms have been processed

    Cases in the queue are moved through the following phases:

      - Phase 1: Accumulate cases touched by forms as they are
        processed. When a sufficiently sized batch of cases that have
        not been seen before has accumulated, move it to phase 2. Cases
        that have previously been loaded by phase 2 are updated in this
        phase, and will be directly enqueued to diff (sent to phase 3)
        when the last form for a case has been processed.
      - Phase 2: Load full case documents from couch to get the list of
        forms touched by each case. The cases are updated with processed
        forms and enqueued to be diffed when all relevant forms have
        been processed.
      - Phase 3: Enqueued cases are accumulated to be diffed in batches.
      - Phase 4: Diff a batch of cases.

    Cases and other internal state of this queue are persisted in the
    state db so they will be preserved between invocations when the
    queue is used as a context manager. Some cases may be diffed more
    than once, but none should be lost on account of of stop/resume.
    """

    BATCH_SIZE = 100

    def __init__(self, statedb, status_interval=STATUS_INTERVAL):
        self.statedb = statedb
        self.status_interval = status_interval
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
        self.num_diffed_cases = 0

    def __enter__(self):
        self._load_resume_state()
        self._stop_status_logger = self.run_status_logger()
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        try:
            if exc_type is None:
                self.process_remaining_diffs()
        finally:
            self._stop_status_logger()
            self._save_resume_state()

    def update(self, case_ids, form_id):
        """Update the case diff queue with case ids touched by form

        :param case_ids: sequence of case ids.
        :param form_id: form id touching case ids.
        """
        log.debug("update: cases=%s form=%s", case_ids, form_id)
        cases = self.cases
        pending = self.pending_cases
        for case_id in case_ids:
            if case_id in cases:
                self._try_to_diff(cases[case_id], [form_id])
            else:
                pending[case_id].add(form_id)
                if len(pending) >= self.BATCH_SIZE:
                    self._add_pending_cases(pending)
                    pending = self.pending_cases = defaultdict(set)
        task_switch()

    def _add_pending_cases(self, pending_cases):
        log.debug("add pending cases %s", pending_cases)
        return self.case_batcher.spawn(self._load_cases, pending_cases)

    def _load_cases(self, pending):
        """Load cases and try to diff them as forms are processed

        :param pending: dict of processed form id sequences (list
        or set) by case id.
        """
        cases = self.cases
        case_ids = list(pending)
        loaded_case_ids = set()
        stock_forms = get_stock_forms_by_case_id(case_ids)
        for case in CaseAccessorCouch.get_cases(case_ids):
            loaded_case_ids.add(case.case_id)
            if case.case_id not in cases:
                case_stock_forms = stock_forms.get(case.case_id, [])
                rec = cases[case.case_id] = CaseRecord(case, case_stock_forms)
            else:
                # It's unlikley, but possible that the case has already
                # been loaded by a concurrent invocation of `_load_cases`
                # in which case we use that one so as not to lose its
                # processed forms.
                rec = cases[case.case_id]
            self._try_to_diff(rec, pending[case.case_id])
        missing = set(case_ids) - loaded_case_ids
        if missing:
            log.error("Found %s missing Couch cases", len(missing))
            self.statedb.add_missing_docs("CommCareCase-couch", missing)

    def _try_to_diff(self, rec, processed_form_ids):
        """Add processed forms to case record and enqueue to diff if possible

        :param rec: CaseRecord
        :param processed_form_ids: sequence of processed form ids.
        """
        log.debug("trying case %s forms %s - %s",
            rec.id, rec.remaining_forms, processed_form_ids)
        rec.add_processed(processed_form_ids)
        if rec.is_unexpected:
            log.info("case %s unexpectedly updated by %s", rec.id, processed_form_ids)
            self.statedb.add_unexpected_diff(rec.id)
        if rec.should_diff:
            self.enqueue(rec.case.to_json())

    def enqueue(self, case_doc):
        case_id = case_doc["_id"]
        self.cases.pop(case_id, None)
        self.cases_to_diff[case_id] = case_doc
        if len(self.cases_to_diff) >= self.BATCH_SIZE:
            self._diff_cases()

    def _diff_cases(self):
        def diff(couch_cases):
            diff_cases(couch_cases, statedb=self.statedb)
            self.num_diffed_cases += len(couch_cases)

        self.diff_batcher.spawn(diff, self.cases_to_diff)
        self.cases_to_diff = {}

    def process_remaining_diffs(self):
        log.debug("process remaining diffs")
        if self.pending_cases:
            add_pending = self._add_pending_cases(self.pending_cases)
            self.pending_cases = defaultdict(set)
            gevent.joinall([add_pending])
        for rec in list(self.cases.values()):
            self.enqueue(rec.case.to_json())
        self._flush()
        self._rediff_unexpected()
        self._flush()
        assert not self.pending_cases, self.pending_cases
        for batcher, action in [
            (self.case_batcher, "loaded"),
            (self.diff_batcher, "diffed"),
        ]:
            if batcher:
                log.warn("%s batches of cases could not be %s", len(batcher), action)
        self.pool = None

    def _flush(self):
        pool = self.pool
        while self.cases_to_diff or pool:
            if self.cases_to_diff:
                self._diff_cases()
            while not pool.join(timeout=10):
                log.info('Waiting on {} case diff workers'.format(len(pool)))

    def _rediff_unexpected(self):
        unexpected = self.statedb.iter_unexpected_diffs()
        for case_ids in chunked(unexpected, self.BATCH_SIZE, list):
            log.debug("re-diff %s", case_ids)
            self.statedb.discard_case_diffs(case_ids)
            self._enqueue_cases(case_ids)

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
        if self.num_diffed_cases:
            state["num_diffed_cases"] = self.num_diffed_cases
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
        if "num_diffed_cases" in state:
            self.num_diffed_cases = state["num_diffed_cases"]

    def _enqueue_cases(self, case_ids):
        for case in CaseAccessorCouch.get_cases(case_ids):
            self.enqueue(case.to_json())

    def run_status_logger(self):
        """Start periodic status logger in a greenlet

        Log status every `self.status_interval` seconds unless it
        evaluates to false, in which case the loop is not started.

        :returns: A function that stops the logger loop.
        """
        def status_logger():
            while not exit.wait(timeout=self.status_interval):
                self.log_status(self.get_status())

        def stop():
            exit.set()
            loop.join()

        if self.status_interval:
            exit = Event()
            loop = gevent.spawn(status_logger)
            return stop
        return lambda: None

    @staticmethod
    def log_status(status):
        log.info(
            "cases diffed=%s, pending cases=%s diffs=%s",
            status["diffed_cases"],
            status["pending_cases"],
            status["pending_diffs"],
        )

    def get_status(self):
        return {
            "pending_cases": (
                len(self.pending_cases)
                + sum(len(batch) for batch in self.case_batcher)
                + len(self.cases)
            ),
            "pending_diffs": (
                len(self.cases_to_diff)
                + sum(len(batch) for batch in self.diff_batcher)
            ),
            "diffed_cases": self.num_diffed_cases,
        }


def task_switch():
    gevent.sleep()


class CaseRecord(object):

    def __init__(self, case, stock_forms):
        self.case = case
        self.remaining_forms = get_case_form_ids(case)
        self.remaining_forms.update(stock_forms)
        self.processed_forms = set()

    @property
    def id(self):
        return self.case.case_id

    def add_processed(self, form_ids):
        for form_id in form_ids:
            try:
                self.remaining_forms.remove(form_id)
            except KeyError:
                pass
            else:
                self.processed_forms.add(form_id)
        if self.is_unexpected:
            self.remaining_forms.clear()

    @property
    def should_diff(self):
        return not self.remaining_forms

    @property
    def is_unexpected(self):
        return not self.processed_forms


def get_case_form_ids(couch_case):
    """Get the set of form ids that touched the given couch case object"""
    form_ids = set(couch_case.xform_ids)
    for action in couch_case.actions:
        if action.xform_id:
            form_ids.add(action.xform_id)
    return form_ids


def get_stock_forms_by_case_id(case_ids):
    """Get a dict of form id sets by case id for the given list of case ids

    This function loads Couch stock forms (even though they are
    technically stored in SQL).
    """
    form_ids_by_case_id = defaultdict(set)
    for case_id, form_id in (
        StockReport.objects
        .filter(stocktransaction__case_id__in=case_ids)
        .values_list("stocktransaction__case_id", "form_id")
        .distinct()
    ):
        form_ids_by_case_id[case_id].add(form_id)
    return form_ids_by_case_id


class BatchProcessor(object):
    """Process batches of items with a worker pool

    Each batch of items is retained until its processing job has
    completed successfully. Unprocessed batches can be retrieved
    by iterating on the processor object.
    """

    MAX_RETRIES = 3

    def __init__(self, pool):
        self.pool = pool
        self.batches = {}
        self.key_gen = count()
        self.retries = defaultdict(int)

    def __repr__(self):
        return "<BatchProcessor {}>".format(self.batches)

    def spawn(self, process, batch):
        key = next(self.key_gen)
        self.batches[key] = batch
        return self._process_batch(process, key)

    def _process_batch(self, process, key):
        def process_batch(key):
            log.debug("call %s key=%s", process.__name__, key)
            try:
                process(self.batches[key])
            except Exception as err:
                log.warn("batch processing error: %s: %s",
                    type(err).__name__, err, exc_info=True)
                if self._should_retry(key):
                    self._process_batch(process, key)
                else:
                    raise
            else:
                self.batches.pop(key)
                self.retries.pop(key, None)

        log.debug("schedule %s key=%s", process.__name__, key)
        return self.pool.spawn(process_batch, key)

    def _should_retry(self, key):
        self.retries[key] += 1
        return self.retries[key] < self.MAX_RETRIES

    def __len__(self):
        """Return the number of unprocessed batches"""
        return len(self.batches)

    def __iter__(self):
        return iter(self.batches.values())


def diff_cases(couch_cases, statedb):
    log.debug('Calculating case diffs for {} cases'.format(len(couch_cases)))
    counts = defaultdict(int)
    case_ids = list(couch_cases)
    sql_cases = CaseAccessorSQL.get_cases(case_ids)
    sql_case_ids = set()
    for sql_case in sql_cases:
        sql_case_ids.add(sql_case.case_id)
        couch_case = couch_cases[sql_case.case_id]
        sql_case_json = sql_case.to_json()
        diffs = json_diff(couch_case, sql_case_json, track_list_indices=False)
        diffs = filter_case_diffs(couch_case, sql_case_json, diffs, statedb)
        if diffs and not sql_case.is_deleted:
            try:
                couch_case, diffs = rebuild_couch_case_and_re_diff(
                    couch_case, sql_case_json, statedb)
            except Exception as err:
                log.warning('Case {} rebuild -> {}: {}'.format(
                    sql_case.case_id, type(err).__name__, err))
        if diffs:
            statedb.add_diffs(couch_case['doc_type'], sql_case.case_id, diffs)
        counts[couch_case['doc_type']] += 1

    diff_ledgers(case_ids, statedb)

    if len(case_ids) != len(sql_case_ids):
        couch_ids = set(case_ids)
        assert not (sql_case_ids - couch_ids), sql_case_ids - couch_ids
        missing_cases = [couch_cases[x] for x in couch_ids - sql_case_ids]
        log.debug("Found %s missing SQL cases", len(missing_cases))
        for doc_type, doc_ids in filter_missing_cases(missing_cases):
            statedb.add_missing_docs(doc_type, doc_ids)
            counts[doc_type] += len(doc_ids)

    for doc_type, count_ in six.iteritems(counts):
        statedb.increment_counter(doc_type, count_)


def rebuild_couch_case_and_re_diff(couch_case, sql_case_json, statedb):
    assert couch_case["domain"] == sql_case_json["domain"], \
        (couch_case["domain"], sql_case_json["domain"])
    rebuilt_case = FormProcessorCouch.hard_rebuild_case(
        couch_case["domain"], couch_case['_id'], None, save=False, lock=False
    )
    rebuilt_case_json = rebuilt_case.to_json()
    diffs = json_diff(rebuilt_case_json, sql_case_json, track_list_indices=False)
    diffs = filter_case_diffs(rebuilt_case_json, sql_case_json, diffs, statedb)
    return rebuilt_case_json, diffs


def diff_ledgers(case_ids, statedb):
    log.debug('Calculating ledger diffs for {} cases'.format(len(case_ids)))
    couch_state_map = {
        state.ledger_reference: state
        for state in StockState.objects.filter(case_id__in=case_ids)
    }
    for ledger_value in LedgerAccessorSQL.get_ledger_values_for_cases(case_ids):
        couch_state = couch_state_map.get(ledger_value.ledger_reference, None)
        diffs = json_diff(couch_state.to_json(), ledger_value.to_json(), track_list_indices=False)
        statedb.add_diffs(
            'stock state', ledger_value.ledger_reference.as_id(),
            filter_ledger_diffs(diffs)
        )


def filter_missing_cases(missing_cases):
    result = defaultdict(list)
    for couch_case in missing_cases:
        if is_orphaned_case(couch_case):
            log.info("Ignoring orphaned case: %s", couch_case["_id"])
        else:
            result[couch_case["doc_type"]].append(couch_case["_id"])
    return six.iteritems(result)


def is_orphaned_case(couch_case):
    def references_case(form_id):
        form = FormAccessorCouch.get_form(form_id)
        try:
            return case_id in get_case_ids_from_form(form)
        except MissingFormXml:
            return True  # assume case is referenced if form XML is missing

    case_id = couch_case["_id"]
    return not any(references_case(x) for x in couch_case["xform_ids"])
