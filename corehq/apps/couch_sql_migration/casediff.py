from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict
from itertools import chain, count

import gevent
import gipc
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
from corehq.form_processor.parsers.ledgers.form import MissingFormXml
from dimagi.utils.chunked import chunked

from .diff import filter_case_diffs, filter_ledger_diffs

log = logging.getLogger(__name__)

STATUS_INTERVAL = 300  # 5 minutes
MAX_FORMS_PER_MEMORIZED_CASE = 20


class CaseDiffQueue(object):
    """A queue that diffs cases when all relevant forms have been processed

    Cases in the queue are moved through the following phases:

      - Phase 0: Receive cases as forms are processed. Accumulate
        in batches to be processed in phase 1.
      - Phase 1: Accumulate cases that have not been seen before. When a
        sufficiently sized batch has accumulated, move it to phase 2.
        Cases that have previously been loaded by phase 2 are updated in
        this phase, and will be directly enqueued to diff (sent to phase
        3) when the last form for a case has been processed.
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
        self.pending_cases = defaultdict(int)  # case id -> processed form count
        self.pending_loads = defaultdict(int)  # case id -> processed form count
        self.cases_to_diff = {}  # case id -> case doc (JSON)
        self.pool = Pool(5)
        self.case_batcher = BatchProcessor(self.pool)
        self.diff_batcher = BatchProcessor(self.pool)
        self.cases = {}
        self.num_diffed_cases = 0
        self._is_flushing = False

    def __enter__(self):
        self._load_resume_state()
        self._stop_status_logger = self.run_status_logger()
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        try:
            if exc_type is None:
                self.process_remaining_diffs()
        finally:
            self._save_resume_state()
            self._stop_status_logger()

    def update(self, case_ids, form_id):
        """Update the case diff queue with case ids touched by form

        :param case_ids: sequence of case ids.
        :param form_id: form id touching case ids.
        """
        log.debug("update: cases=%s form=%s", case_ids, form_id)
        pending = self.pending_cases
        for case_id in case_ids:
            pending[case_id] += 1
            if len(pending) >= self.BATCH_SIZE:
                self._async_enqueue_or_load(pending)
                pending = self.pending_cases = defaultdict(int)
        task_switch()

    def _async_enqueue_or_load(self, pending):
        self.case_batcher.spawn(self._enqueue_or_load, pending)

    def _enqueue_or_load(self, pending):
        """Enqueue or load pending cases

        Update processed form counts and enqueue cases to be diffed when
        all corresponding forms have been processed. Accumulate a batch
        of unknown cases and spawn it to be loaded once big enough.

        :param pending: dict `{<case_id>: <processed_form_count>, ...}`
        """
        log.debug("enqueue or load %s", pending)
        to_diff = []
        batch = self.pending_loads
        result = self.statedb.add_processed_forms(pending)
        for case_id, total_forms, processed_forms in result:
            if total_forms is None:
                batch[case_id] += pending[case_id]
                if len(batch) >= self.BATCH_SIZE:
                    self._async_load_cases(batch)
                    batch = self.pending_loads = defaultdict(int)
            elif total_forms <= processed_forms:
                to_diff.append(case_id)
        if self._is_flushing and batch:
            self._load_cases(batch)
            self.pending_loads = defaultdict(int)
        if to_diff:
            self._enqueue_cases(to_diff)

    def _async_load_cases(self, pending):
        self.case_batcher.spawn(self._load_cases, pending)

    def _load_cases(self, pending):
        """Load cases and establish total and processed form counts

        Cases for which all forms have been processed are enqueued to be
        diffed.

        :param pending: dict `{<case_id>: <processed_form_count>, ...}`
        """
        log.debug("enqueue or load %s", pending)
        cases = self.cases
        case_ids = list(pending)
        loaded_cases = {}
        case_records = []
        enqueued = set()
        stock_forms = get_stock_forms_by_case_id(case_ids)
        for case in CaseAccessorCouch.get_cases(case_ids):
            loaded_cases[case.case_id] = case
            case_stock_forms = stock_forms.get(case.case_id, [])
            rec = CaseRecord(case, case_stock_forms, pending[case.case_id])
            case_records.append(rec)
            if rec.should_memorize_case:
                log.debug("memorize %s", rec)
                cases[case.case_id] = case
        if case_records:
            result = self.statedb.update_cases(case_records)
            for case_id, total_forms, processed_forms in result:
                if total_forms <= processed_forms and case_id not in enqueued:
                    self.enqueue(loaded_cases[case_id].to_json())
        missing = set(case_ids) - set(loaded_cases)
        if missing:
            log.error("Found %s missing Couch cases", len(missing))
            self.statedb.add_missing_docs("CommCareCase-couch", missing)

    def _enqueue_cases(self, case_ids):
        log.debug("enqueue cases %s", case_ids)
        to_load = []
        get_case = self.cases.get
        for case_id in case_ids:
            case = get_case(case_id)
            if case is None:
                to_load.append(case_id)
            else:
                self.enqueue(case.to_json())
        for case in CaseAccessorCouch.get_cases(to_load):
            self.enqueue(case.to_json())

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
        self.flush()
        for batcher, action in [
            (self.case_batcher, "loaded"),
            (self.diff_batcher, "diffed"),
        ]:
            if batcher:
                log.warn("%s batches of cases could not be %s", len(batcher), action)
        self.pool = None

    def flush(self, complete=True):
        """Process cases in the queue

        :param complete: diff cases with unprocessed forms if true (the default)
        """
        def join(pool):
            while not pool.join(timeout=10):
                log.info('Waiting on {} case diff workers'.format(len(pool)))

        log.debug("begin flush")
        pool = self.pool
        self._is_flushing = True
        try:
            if self.pending_cases:
                self._enqueue_or_load(self.pending_cases)
                self.pending_cases = defaultdict(int)
            join(pool)
            if complete:
                to_diff = self.statedb.iter_cases_with_unprocessed_forms()
                for chunk in chunked(to_diff, self.BATCH_SIZE, list):
                    self._enqueue_cases(chunk)
            while self.cases_to_diff or pool:
                if self.cases_to_diff:
                    self._diff_cases()
                join(pool)
            assert not self.pending_cases, self.pending_cases
            assert not self.pending_loads, self.pending_loads
        finally:
            self._is_flushing = False
        log.debug("end flush")

    def _save_resume_state(self):
        state = {}
        if self.pending_cases or self.pending_loads or self.case_batcher:
            pending = defaultdict(int, self.pending_cases)
            for batch in chain(self.case_batcher, [self.pending_loads]):
                for case_id, processed_forms in batch.items():
                    pending[case_id] += processed_forms
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
                self._async_load_cases(dict(chunk))
        if "num_diffed_cases" in state:
            self.num_diffed_cases = state["num_diffed_cases"]

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
                + len(self.pending_loads)
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

    def __init__(self, case, stock_forms, processed_forms):
        self.id = case.case_id
        case_forms = get_case_form_ids(case)
        self.total_forms = len(case_forms) + len(stock_forms)
        self.processed_forms = processed_forms

    def __repr__(self):
        return "case {id} with {n} of {m} forms processed".format(
            id=self.id,
            n=self.processed_forms,
            m=self.total_forms,
        )

    @property
    def should_memorize_case(self):
        # do not keep cases with large history in memory
        return self.total_forms <= MAX_FORMS_PER_MEMORIZED_CASE


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


class CaseDiffProcess(object):
    """Run CaseDiffQueue in a separate process"""

    def __init__(self, statedb, status_interval=STATUS_INTERVAL, queue_class=CaseDiffQueue):
        self.statedb = statedb
        self.status_interval = status_interval
        self.queue_class = queue_class

    def __enter__(self):
        log.debug("starting case diff process")
        self.calls_pipe = gipc.pipe()
        self.stats_pipe = gipc.pipe()
        calls, self.calls = self.calls_pipe.__enter__()
        self.stats, stats = self.stats_pipe.__enter__()
        args = (self.queue_class, calls, stats, self.statedb)
        self.process = gipc.start_process(target=run_case_diff_queue, args=args)
        self.status_logger = gevent.spawn(self.run_status_logger)
        return self

    def __exit__(self, *exc_info):
        is_error = exc_info[0] is not None
        if is_error:
            log.error("stopping process with error", exc_info=exc_info)
        else:
            log.debug("stopping process")
        self.calls.put((TERMINATE, is_error))
        self.status_logger.join(timeout=30)
        self.process.join(timeout=30)
        self.stats_pipe.__exit__(*exc_info)
        self.calls_pipe.__exit__(*exc_info)

    def update(self, case_ids, form_id):
        self.calls.put(("update", case_ids, form_id))

    def enqueue(self, case_doc):
        self.calls.put(("enqueue", case_doc))

    def request_status(self):
        log.debug("reqeust status...")
        self.calls.put((STATUS,))

    def run_status_logger(self):
        """Request and log status from the case diff process

        Status details are logged as they are produced by the remote
        process. A status update is requested when the remote process
        has not sent an update in `status_interval` seconds.
        """
        requested = object()
        status = None
        while True:
            with gevent.Timeout(self.status_interval, False) as timeout:
                status = self.stats.get(timeout=timeout)
            if status == TERMINATE:
                break
            if status is None:
                self.request_status()
                status = requested
            elif status is not requested:
                CaseDiffQueue.log_status(status)
                status = None


STATUS = "status"
TERMINATE = "terminate"


def run_case_diff_queue(queue_class, calls, stats, statedb):
    def status():
        stats.put(queue.get_status())

    def terminate(is_error):
        stats.put(TERMINATE)
        raise (ParentError if is_error else GracefulExit)

    def dispatch(action, *args):
        log.debug("case diff dispatch: %s", action)
        if action in process_actions:
            process_actions[action](*args)
        else:
            getattr(queue, action)(*args)

    process_actions = {STATUS: status, TERMINATE: terminate}
    try:
        with queue_class(statedb, status_interval=0) as queue, calls, stats:
            try:
                while True:
                    call = calls.get()
                    dispatch(*call)
            except GracefulExit:
                pass
    except ParentError:
        log.error("stopped due to error in parent process")


class GracefulExit(Exception):
    pass


class ParentError(Exception):
    pass


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
