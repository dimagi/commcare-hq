import logging
import os
import signal
import sys
from contextlib import contextmanager

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import attr

from dimagi.utils.chunked import chunked

from corehq.apps.commtrack.models import StockState
from corehq.apps.domain.models import Domain
from corehq.apps.tzmigration.timezonemigration import json_diff
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    LedgerAccessorSQL,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import set_local_domain_sql_backend_override
from corehq.util.log import with_progress_bar

from ...casediff import ProcessNotAllowed, filter_missing_cases, get_casediff_state_path
from ...couchsqlmigration import (
    CouchSqlDomainMigrator,
    get_main_forms_iteration_stop_date,
    migration_patches,
    setup_logging,
)
from ...diff import filter_case_diffs, filter_ledger_diffs
from ...parallel import Pool
from ...rebuildcase import (
    is_action_order_equal,
    rebuild_case_with_couch_action_order,
    was_rebuilt,
)
from ...util import get_ids_from_string_or_file

log = logging.getLogger(__name__)

DIFF_BATCH_SIZE = 100
PENDING_WARNING = "Diffs pending. Run again with --cases=pending"


class Command(BaseCommand):
    help = "Diff data in couch and SQL with parallel worker processes"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--no-input', action='store_true', default=False)
        parser.add_argument('--debug', action='store_true', default=False)
        parser.add_argument('--state-dir',
            default=os.environ.get("CCHQ_MIGRATION_STATE_DIR"),
            required="CCHQ_MIGRATION_STATE_DIR" not in os.environ,
            help="""
                Directory for couch2sql logs and migration state. This must not
                reside on an NFS volume for migration state consistency.
                Can be set in environment: CCHQ_MIGRATION_STATE_DIR
            """)
        parser.add_argument('--live',
            dest="live", action='store_true', default=False,
            help='''
                Do not diff cases modified after the most recently
                migrated form.
            ''')
        parser.add_argument('--cases',
            help='''
                Diff specific cases. The value of this option should
                be 'pending' to clear out in-process diffs OR a
                space-delimited list of case ids OR a path to a file
                containing a case id on each line. The path must begin
                with / or ./
            ''')

    def handle(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError('It looks like {} has already been migrated.'.format(domain))

        for opt in ["no_input", "state_dir", "live", "cases"]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')

        assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        setup_logging(self.state_dir, "case_diff", options['debug'])
        migrator = get_migrator(domain, self.state_dir, self.live)
        msg = do_case_diffs(migrator, self.cases)
        if msg:
            sys.exit(msg)


def get_migrator(domain, state_dir, live):
    # Set backend for CouchSqlDomainMigrator._check_for_migration_restrictions
    set_local_domain_sql_backend_override(domain)
    return CouchSqlDomainMigrator(
        domain, state_dir, live_migrate=live, diff_process=None)


def do_case_diffs(migrator, cases):
    def save_result(data):
        log.debug(data)
        add_cases(len(data.doc_ids))
        statedb.add_diffed_cases(data.doc_ids)
        for doc_type, doc_id, diffs in data.diffs:
            if doc_type == "stock state":
                statedb.add_diffs(doc_type, doc_id, diffs)
            else:
                statedb.replace_case_diffs(doc_type, doc_id, diffs)
        for doc_type, doc_ids in data.missing_docs:
            statedb.add_missing_docs(doc_type, doc_ids)

    casediff = CaseDiffTool(migrator, cases)
    statedb = casediff.statedb
    with casediff.context() as add_cases:
        for data in casediff.iter_case_diff_results():
            save_result(data)
    if casediff.should_diff_pending():
        return PENDING_WARNING


class CaseDiffTool:

    def __init__(self, migrator, cases):
        self.migrator = migrator
        self.domain = migrator.domain
        self.statedb = migrator.statedb
        self.cases = cases
        if not migrator.live_migrate:
            cutoff_date = None
        elif hasattr(migrator.stopper, "stop_date"):
            cutoff_date = migrator.stopper.stop_date
        else:
            cutoff_date = get_main_forms_iteration_stop_date(
                self.domain, self.statedb.unique_id)
            migrator.stopper.stop_date = cutoff_date
        self.cutoff_date = cutoff_date
        self.lock_out_casediff_process()

    def lock_out_casediff_process(self):
        if not self.statedb.get(ProcessNotAllowed.__name__):
            state_path = get_casediff_state_path(self.statedb.db_filepath)
            if os.path.exists(state_path):
                self.statedb.clone_casediff_data_from(state_path)
            self.statedb.set(ProcessNotAllowed.__name__, True)

    @contextmanager
    def context(self):
        with self.migrator.counter as counter, self.migrator.stopper:
            with counter('diff_cases', 'CommCareCase') as add_cases:
                yield add_cases

    def iter_case_diff_results(self):
        if self.cases is None:
            return self.resumable_iter_diff_cases()
        if self.cases == "pending":
            return self.iter_diff_pending_cases()
        return self.iter_diff_specific_cases()

    def iter_diff_specific_cases(self):
        case_ids = get_ids_from_string_or_file(self.cases)
        batches = chunked(case_ids, DIFF_BATCH_SIZE, list)
        with init_worker(*self.initargs):
            for batch in batches:
                yield diff_cases(batch, log_cases=True)

    def resumable_iter_diff_cases(self):
        batches = chunked(self.iter_case_ids(), DIFF_BATCH_SIZE, self.diff_batch)
        yield from self.pool.imap_unordered(diff_cases, batches)

    def iter_diff_pending_cases(self):
        def list_or_stop(items):
            if self.is_stopped():
                raise StopIteration
            return list(items)

        pending = self.get_pending_cases()
        batches = chunked(pending, DIFF_BATCH_SIZE, list_or_stop)
        yield from self.pool.imap_unordered(diff_cases, batches)

    def diff_batch(self, case_ids):
        case_ids = list(case_ids)
        self.statedb.add_cases_to_diff(case_ids)
        return case_ids

    def is_stopped(self):
        return self.migrator.stopper.clean_break

    def iter_case_ids(self):
        return self.migrator._get_resumable_iterator(
            ['CommCareCase.id'],
            progress_name="Diff",
            offset_key='CommCareCase.id',
        )

    def get_pending_cases(self):
        count = self.statedb.count_undiffed_cases()
        if not count:
            return []
        pending = self.statedb.iter_undiffed_case_ids()
        return with_progress_bar(
            pending, count, prefix="Pending case diffs", oneline=False)

    def should_diff_pending(self):
        return self.cases is None and self.get_pending_cases()

    @property
    def pool(self):
        return Pool(initializer=init_worker, initargs=self.initargs, maxtasksperchild=100)

    @property
    def initargs(self):
        return self.domain, self.statedb.get_no_action_case_forms(), self.cutoff_date


def diff_cases(case_ids, log_cases=False):
    couch_cases = {c.case_id: c.to_json()
        for c in CaseAccessorCouch.get_cases(case_ids) if _state.should_diff(c)}
    if log_cases:
        skipped = [id for id in case_ids if id not in couch_cases]
        log.info("skipping cases modified since cutoff date: %s", skipped)
    case_ids = list(couch_cases)
    data = DiffData()
    sql_case_ids = set()
    for sql_case in CaseAccessorSQL.get_cases(case_ids):
        case_id = sql_case.case_id
        sql_case_ids.add(case_id)
        couch_case = couch_cases[case_id]
        try:
            diffs = diff_case(sql_case, couch_case)
        except Exception:
            log.exception("cannot diff case %s", case_id)
            continue
        data.doc_ids.append(case_id)
        data.diffs.append((couch_case['doc_type'], case_id, diffs))
        if log_cases:
            log.info("case %s -> %s diffs", case_id, len(diffs))

    data.diffs.extend(iter_ledger_diffs(case_ids))
    add_missing_docs(data, couch_cases, sql_case_ids)
    return data


def diff_case(sql_case, couch_case):
    def diff(couch_json, sql_json):
        diffs = json_diff(couch_json, sql_json, track_list_indices=False)
        return filter_case_diffs(couch_json, sql_json, diffs, _state)
    sql_json = sql_case.to_json()
    diffs = diff(couch_case, sql_json)
    if diffs:
        couch_case = FormProcessorCouch.hard_rebuild_case(
            couch_case["domain"], couch_case['_id'], None, save=False, lock=False
        ).to_json()
        diffs = diff(couch_case, sql_json)
        if diffs and should_sort_sql_transactions(sql_case, couch_case):
            sql_case = rebuild_case_with_couch_action_order(sql_case)
            diffs = diff(couch_case, sql_case.to_json())
    return diffs


def should_sort_sql_transactions(sql_case, couch_case):
    return (
        not was_rebuilt(sql_case)
        and not is_action_order_equal(sql_case, couch_case)
    )


def iter_ledger_diffs(case_ids):
    couch_state_map = {
        state.ledger_reference: state
        for state in StockState.objects.filter(case_id__in=case_ids)
    }
    for ledger_value in LedgerAccessorSQL.get_ledger_values_for_cases(case_ids):
        couch_state = couch_state_map.get(ledger_value.ledger_reference, None)
        couch_json = couch_state.to_json() if couch_state is not None else {}
        diffs = json_diff(couch_json, ledger_value.to_json(), track_list_indices=False)
        ref_id = ledger_value.ledger_reference.as_id()
        yield "stock state", ref_id, filter_ledger_diffs(diffs)


def add_missing_docs(data, couch_cases, sql_case_ids):
    if len(couch_cases) != len(sql_case_ids):
        only_in_sql = sql_case_ids - couch_cases.keys()
        assert not only_in_sql, only_in_sql
        only_in_couch = couch_cases.keys() - sql_case_ids
        data.doc_ids.extend(only_in_couch)
        missing_cases = [couch_cases[x] for x in only_in_couch]
        log.debug("Found %s missing SQL cases", len(missing_cases))
        for doc_type, doc_ids in filter_missing_cases(missing_cases):
            data.missing_docs.append((doc_type, doc_ids))


def init_worker(domain, *args):
    def on_break(signum, frame):
        nonlocal clean_break
        if clean_break:
            raise KeyboardInterrupt
        print("clean break... (Ctrl+C to abort)")
        clean_break = True

    global _state
    _state = WorkerState(*args)
    clean_break = False
    signal.signal(signal.SIGINT, on_break)
    set_local_domain_sql_backend_override(domain)
    return migration_patches()


@attr.s
class DiffData:
    doc_ids = attr.ib(factory=list)
    diffs = attr.ib(factory=list)
    missing_docs = attr.ib(factory=list)


@attr.s
class WorkerState:
    forms = attr.ib(repr=lambda v: f"[{len(v)} ids]")
    cutoff_date = attr.ib()

    def __attrs_post_init__(self):
        if self.cutoff_date is None:
            self.should_diff = lambda case: True

    def get_no_action_case_forms(self):
        return self.forms

    def should_diff(self, case):
        return case.server_modified_on < self.cutoff_date
