import logging
import os
import signal
from collections import defaultdict
from contextlib import ExitStack
from functools import partial
from itertools import chain, count

import gevent
import gipc
from gevent.pool import Group, Pool

from casexml.apps.stock.models import StockReport
from dimagi.utils.chunked import chunked

from corehq.apps.tzmigration.timezonemigration import FormJsonDiff as Diff, MISSING

from .casediff import (
    diff_cases_and_save_state,
    get_couch_cases,
    global_diff_state,
)
from .lrudict import LRUDict
from .statedb import StateDB
from .status import run_status_logger
from .util import ProcessError, exit_on_error, gipc_process_error_handler

log = logging.getLogger(__name__)

STATUS_INTERVAL = 300  # 5 minutes
MAX_FORMS_PER_MEMORIZED_CASE = 20
MAX_FORMS_PER_DIFF = 1000


class CaseDiffQueue:
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
    MAX_DIFF_WORKERS = 10
    MAX_MEMORIZED_CASES = 4096

    def __init__(self, statedb, status_interval=STATUS_INTERVAL):
        assert self.BATCH_SIZE < self.MAX_MEMORIZED_CASES, \
            (self.BATCH_SIZE, self.MAX_MEMORIZED_CASES)
        self.statedb = statedb
        self.status_interval = status_interval
        self.pending_cases = defaultdict(int)  # case id -> processed form count
        self.pending_loads = defaultdict(int)  # case id -> processed form count
        self.cases_to_diff = {}  # case id ready to diff -> form count
        self.pool = Group()
        # The diff pool is used for case diff jobs. It has limited
        # concurrency to prevent OOM conditions caused by loading too
        # many cases into memory. The approximate limit on number of
        # couch cases in memory at any time
        # BATCH_SIZE + MAX_MEMORIZED_CASES + MAX_DIFF_WORKERS * BATCH_SIZE
        self.diff_pool = Pool(self.MAX_DIFF_WORKERS)
        self.case_batcher = BatchProcessor(self.pool)
        self.diff_spawner = BatchProcessor(self.pool)
        self.diff_batcher = BatchProcessor(self.diff_pool)
        self.cases = LRUDict(self.MAX_MEMORIZED_CASES)
        self.num_diffed_cases = 0
        self.cache_hits = [0, 0]
        self.clean_break = False
        self._is_flushing = False

    def __enter__(self):
        self.statedb.set(ProcessNotAllowed.__name__, True)
        with self.statedb.pop_resume_state(type(self).__name__, {}) as state:
            self._load_resume_state(state)
        self._stop_status_logger = run_status_logger(
            log_status, self.get_status, self.status_interval)
        domain = self.statedb.domain
        get_forms = self.statedb.get_no_action_case_forms
        self._global_state = ExitStack()
        self._global_state.enter_context(global_diff_state(domain, get_forms))
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        try:
            if exc_type is None:
                self.process_remaining_diffs()
            log.info("preparing to save resume state... DO NOT BREAK!")
        finally:
            self._global_state.close()
            self._save_resume_state()
            self._stop_status_logger()

    def update(self, case_ids, form_id):
        """Update the case diff queue with case ids touched by form

        :param case_ids: sequence of case ids.
        :param form_id: form id touching case ids.
        """
        log.debug("update: cases=%s form=%s", case_ids, form_id)
        pending = self.pending_cases
        increment = 0 if form_id is None else 1
        for case_id in case_ids:
            pending[case_id] += increment
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
        update_lru = self.cases.get
        batch = self.pending_loads
        result = self.statedb.add_processed_forms(pending)
        for case_id, total_forms, processed_forms in result:
            if total_forms is None:
                batch[case_id] += pending[case_id]
                if len(batch) >= self.BATCH_SIZE:
                    self._async_load_cases(batch)
                    batch = self.pending_loads = defaultdict(int)
            elif total_forms <= processed_forms:
                self.enqueue(case_id, processed_forms)
            else:
                update_lru(case_id)
        if self._is_flushing and batch:
            self._load_cases(batch)
            self.pending_loads = defaultdict(int)

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
        loaded_case_ids = set()
        case_records = []
        stock_forms = get_stock_forms_by_case_id(case_ids)
        for case in get_couch_cases(case_ids):
            loaded_case_ids.add(case.case_id)
            case_stock_forms = stock_forms.get(case.case_id, [])
            rec = CaseRecord(case, case_stock_forms, pending[case.case_id])
            case_records.append(rec)
            if rec.should_memorize_case:
                log.debug("memorize %s", rec)
                cases[case.case_id] = case
        if case_records:
            result = self.statedb.update_cases(case_records)
            for case_id, total_forms, processed_forms in result:
                if total_forms <= processed_forms:
                    self.enqueue(case_id, processed_forms)
        missing = set(case_ids) - loaded_case_ids
        if missing:
            log.error("Found %s missing Couch cases", len(missing))
            self.statedb.replace_case_diffs([(
                "CommCareCase",
                case_id,
                [Diff("missing", path=["*"], old_value=MISSING, new_value="?")],
            ) for case_id in missing])

    def enqueue(self, case_id, num_forms=None):
        if num_forms is None:
            num_forms = self.statedb.get_forms_count(case_id)
        if self.cases_to_diff:
            total_forms = sum(self.cases_to_diff.values()) + num_forms
            if total_forms > MAX_FORMS_PER_DIFF:
                self._diff_cases()
        self.cases_to_diff[case_id] = num_forms
        if len(self.cases_to_diff) >= self.BATCH_SIZE or num_forms > MAX_FORMS_PER_DIFF:
            self._diff_cases()

    def _diff_cases(self):
        def diff(case_ids):
            couch_cases = []
            to_load = []
            pop_case = self.cases.pop
            for case_id in case_ids:
                case = pop_case(case_id, None)
                if case is None:
                    to_load.append(case_id)
                else:
                    couch_cases.append(case)
            popped_cases = list(couch_cases)
            couch_cases.extend(get_couch_cases(to_load))
            prune = (iter if self._is_flushing
                else partial(prune_premature_diffs, statedb=self.statedb))
            json_by_id = {c.case_id: c.to_json() for c in prune(couch_cases)}
            restore_cached(popped_cases, json_by_id)
            if json_by_id:
                diff_cases_and_save_state(json_by_id, statedb=self.statedb)
                self.cache_hits[0] += len(json_by_id.keys() - to_load)
                self.cache_hits[1] += len(json_by_id)
                self.num_diffed_cases += len(json_by_id)

        def restore_cached(popped_cases, diff_ids):
            for case in popped_cases:
                if case.case_id not in diff_ids:
                    self.cases[case.case_id] = case

        def spawn_diff(case_ids):
            # may block due to concurrency limit on diff pool
            self.diff_batcher.spawn(diff, case_ids)

        self.diff_spawner.spawn(spawn_diff, list(self.cases_to_diff))
        self.cases_to_diff = {}

    def process_remaining_diffs(self):
        log.debug("process remaining diffs")
        self.flush(complete=not self.clean_break)
        for batcher, action in [
            (self.case_batcher, "loaded"),
            (self.diff_spawner, "spawned to diff"),
            (self.diff_batcher, "diffed"),
        ]:
            if batcher:
                log.warn("%s batches of cases could not be %s", len(batcher), action)
        self.pool = None
        self.diff_pool = None

    def flush(self, complete=True):
        """Process cases in the queue

        :param complete: diff cases with unprocessed forms if true (the default)
        """
        def join(pool):
            while not pool.join(timeout=10):
                log.info('Waiting on {} case diff workers'.format(len(pool)))

        log.debug("begin flush")
        pool = self.pool
        diff_pool = self.diff_pool
        self._is_flushing = True
        try:
            if self.pending_cases:
                self._enqueue_or_load(self.pending_cases)
                self.pending_cases = defaultdict(int)
            join(pool)
            if complete:
                log.info("Diffing cases with unprocessed forms...")
                unproc = self.statedb.iter_cases_with_unprocessed_forms()
                for case_id, num_forms in unproc:
                    self.enqueue(case_id, num_forms)
            while self.cases_to_diff or pool or diff_pool:
                if self.cases_to_diff:
                    self._diff_cases()
                join(pool)
                join(diff_pool)
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
        if self.diff_batcher or self.diff_spawner or self.cases_to_diff:
            # use dict to approximate ordered set (remove duplicates)
            to_diff = dict.fromkeys(chain.from_iterable(self.diff_batcher))
            to_diff.update((k, None) for k in chain.from_iterable(self.diff_spawner))
            to_diff.update(self.cases_to_diff)
            state["to_diff"] = list(to_diff)
        if self.num_diffed_cases:
            state["num_diffed_cases"] = self.num_diffed_cases
        try:
            self.statedb.set_resume_state(type(self).__name__, state)
        except Exception:
            log.warning("unable to save state\n%r", state)
            raise
        log_state = state if log.isEnabledFor(logging.DEBUG) else {
            k: len(v) if hasattr(v, "__len__") else v for k, v in state.items()
        }
        log.info("saved %s state: %s", type(self).__name__, log_state)

    def _load_resume_state(self, state):
        if "num_diffed_cases" in state:
            self.num_diffed_cases = state["num_diffed_cases"]
        if "to_diff" in state:
            for case_id in state["to_diff"]:
                self.enqueue(case_id)
        if "pending" in state:
            for chunk in chunked(state["pending"].items(), self.BATCH_SIZE, list):
                self._async_load_cases(dict(chunk))

    def get_status(self):
        cache_hits, self.cache_hits = self.cache_hits, [0, 0]
        return {
            "workers": len(self.pool or []) + len(self.diff_pool or []),
            "pending": (
                len(self.pending_cases)
                + len(self.pending_loads)
                + sum(len(batch) for batch in self.case_batcher)
                + len(self.cases_to_diff)
                + sum(len(batch) for batch in self.diff_spawner)
            ),
            "cached": "%s/%s" % tuple(cache_hits),
            "loaded": (
                len(self.cases)
                + sum(len(batch) for batch in self.diff_batcher)
                # subtract diff_spawner jobs because it blocks until
                # diff_batcher starts the job; during that time
                # batches will appear in both
                - sum(len(batch) for batch in self.diff_spawner)
            ),
            "diffed": self.num_diffed_cases,
        }


def log_status(status):
    log.info("cases pending=%(pending)s cached=%(cached)s "
             "loaded=%(loaded)s workers=%(workers)s diffed=%(diffed)s", status)


def task_switch():
    gevent.sleep()


class BatchProcessor:
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

    @exit_on_error
    def _process_batch(self, process, key):
        @exit_on_error
        def process_batch(key):
            log.debug("call %s key=%s", process.__name__, key)
            try:
                process(self.batches[key])
            except Exception as err:
                if self._should_retry(key):
                    log.warn("retrying batch on error: %s: %s",
                        type(err).__name__, err)
                    gevent.spawn(self._process_batch, process, key)
                else:
                    log.exception("batch processing error: %s: %s",
                        type(err).__name__, err)
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


class CaseDiffProcess:
    """Run CaseDiffQueue in a separate process"""

    def __init__(self, statedb, queue_class=CaseDiffQueue):
        if statedb.get(ProcessNotAllowed.__name__):
            raise ProcessNotAllowed(f"{statedb.db_filepath} was previously "
                "used directly by CaseDiffQueue")
        self.statedb = statedb
        self.state_path = get_casediff_state_path(statedb.db_filepath)
        self.status_interval = STATUS_INTERVAL
        self.queue_class = queue_class
        self.num_cases_sent = 0

    def __enter__(self):
        log.debug("starting case diff process")
        self.calls_pipe = gipc.pipe()
        self.stats_pipe = gipc.pipe()
        calls, self.calls = self.calls_pipe.__enter__()
        self.stats, stats = self.stats_pipe.__enter__()
        debug = log.isEnabledFor(logging.DEBUG)
        is_rebuild = self.statedb.is_rebuild
        args = (
            self.queue_class,
            calls,
            stats,
            self.statedb.domain,
            self.state_path,
            is_rebuild,
            debug,
        )
        self.process = gipc.start_process(target=run_case_diff_queue, args=args)
        self.status_logger = gevent.spawn(self.run_status_logger)
        return self

    def __exit__(self, *exc_info):
        is_error = exc_info[0] is not None
        if is_error:
            if isinstance(exc_info[1], ProcessError):
                return
            log.error("stopping process with error", exc_info=exc_info)
        else:
            log.info("stopping case diff process")
        self.request_status()
        self.calls.put((TERMINATE, is_error))
        self.status_logger.join()
        self.process.join(timeout=30)
        self.statedb.clone_casediff_data_from(self.state_path)
        log.info("casediff state copied to %s", self.statedb)
        self.stats_pipe.__exit__(*exc_info)
        self.calls_pipe.__exit__(*exc_info)

    @gipc_process_error_handler()
    def update(self, case_ids, form_id):
        self.num_cases_sent += len(case_ids)
        self.calls.put(("update", case_ids, form_id))

    @gipc_process_error_handler()
    def enqueue(self, case_id):
        self.num_cases_sent += 1
        self.calls.put(("enqueue", case_id))

    @gipc_process_error_handler()
    def request_status(self):
        log.debug("reqeust status...")
        self.calls.put((STATUS,))

    def log_status(self, status):
        sending = self.num_cases_sent - status.pop("received")
        if sending:
            status["pending"] = f"{sending}+{status['pending']}"
        log_status(status)

    @exit_on_error
    def run_status_logger(self):
        """Request and log status from the case diff process

        Status details are logged as they are produced by the remote
        process. A status update is requested when the remote process
        has not sent an update in `status_interval` seconds.
        """
        self.request_status()
        result = requested = object()
        action = STATUS
        while action != TERMINATE:
            with gevent.Timeout(self.status_interval, False) as timeout, \
                    gipc_process_error_handler():
                result = self.stats.get(timeout=timeout)
            if result is None:
                self.request_status()
                result = requested
            elif result is not requested:
                action, status = result
                self.log_status(status)
                result = None
        log.info("casediff process status logger terminated")


STATUS = "status"
TERMINATE = "terminate"


def get_casediff_state_path(path):
    assert os.path.exists(os.path.dirname(path)), path
    assert path.endswith(".db"), path
    return path[:-3] + "-casediff.db"


def run_case_diff_queue(queue_class, calls, stats, domain, state_path, is_rebuild, debug):
    def status():
        stats.put((STATUS, queue.get_status()))

    def terminate(is_error):
        raise (ParentError if is_error else GracefulExit)

    def consume(calls, stop=False):
        while True:
            action, *args = calls.get()
            if stop and action != STATUS:
                log.warning("ignoring %s%r", action, args)
            else:
                dispatch(action, *args)

    def dispatch(action, *args):
        log.debug("case diff dispatch: %s", action)
        if action in process_actions:
            process_actions[action](*args)
        else:
            getattr(queue, action)(*args)

    def on_break(signum, frame):
        if queue.clean_break:
            raise KeyboardInterrupt
        log.info("clean break... (Ctrl+C to abort)")
        queue.clean_break = True

    signal.signal(signal.SIGINT, on_break)
    process_actions = {STATUS: status, TERMINATE: terminate}
    statedb = StateDB.init(domain, state_path)
    statedb.is_rebuild = is_rebuild
    setup_logging(state_path, debug)
    queue = None
    consumer = None
    with calls, stats:
        try:
            with queue_class(statedb, status_interval=0) as queue:
                queue = CasesReceivedCounter(queue)
                try:
                    consume(calls)
                except GracefulExit:
                    pass
                finally:
                    consumer = gevent.spawn(consume, calls, stop=True)
            if consumer is not None:
                consumer.kill()
        except ParentError:
            log.error("stopped due to error in parent process")
        except Exception:
            log.exception("unexpected error")
        finally:
            if queue is not None:
                status_ = queue.get_status()
                log.info("termination status: %s", status_)
                stats.put((TERMINATE, status_))


def setup_logging(state_path, debug):
    from .couchsqlmigration import setup_logging
    state_dir = os.path.dirname(state_path)
    if os.path.basename(state_dir) == "db":
        # unfortunately coupled to _get_state_db_filepath, which adds /db/
        state_dir = os.path.dirname(state_dir)
    setup_logging(state_dir, "casediff", debug)


class GracefulExit(Exception):
    pass


class ParentError(Exception):
    pass


class ProcessNotAllowed(Exception):
    pass


class CasesReceivedCounter:

    def __init__(self, queue):
        self.queue = queue
        self.num_cases_received = 0

    def update(self, case_ids, form_id):
        self.num_cases_received += len(case_ids)
        self.queue.update(case_ids, form_id)

    def enqueue(self, case_id):
        self.num_cases_received += 1
        self.queue.enqueue(case_id)

    def get_status(self):
        status = self.queue.get_status()
        status["received"] = self.num_cases_received
        return status

    @property
    def clean_break(self):
        return self.queue.clean_break

    @clean_break.setter
    def clean_break(self, value):
        self.queue.clean_break = value


class CaseDiffPending:

    def __init__(self, statedb):
        self.statedb = statedb

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    def update(self, case_ids, form_id):
        self.statedb.add_cases_to_diff(case_ids)

    def enqueue(self, case_id):
        self.statedb.add_cases_to_diff([case_id])


def prune_premature_diffs(couch_cases, statedb):
    n_forms = 0
    case_ids = []
    cases_by_id = {c.case_id: c for c in couch_cases}
    stock_forms = get_stock_forms_by_case_id(list(cases_by_id))
    recs = [CaseRecord(c, stock_forms.get(c.case_id, [])) for c in couch_cases]
    for case_id, total_forms, processed_forms in statedb.update_cases(recs):
        if total_forms <= processed_forms:
            yield cases_by_id[case_id]
            case_ids.append(case_id)
            n_forms += total_forms
        else:
            log.debug("pruned premature diff: %s (%s total > %s processed)",
                case_id, total_forms, processed_forms)
    if n_forms > MAX_FORMS_PER_DIFF * 5:
        # maybe adjust MAX_FORMS_PER_DIFF if this is frequent
        cid = case_ids[0] if len(case_ids) == 1 else case_ids
        log.warning("diff case %s with %s forms", cid, n_forms)


class CaseRecord:

    def __init__(self, case, stock_forms, processed_forms=0):
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
