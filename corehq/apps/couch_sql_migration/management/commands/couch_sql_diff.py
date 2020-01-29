import logging
import os
import pdb
import signal
import sys
from contextlib import contextmanager, suppress

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dimagi.utils.chunked import chunked

from corehq.apps.domain.models import Domain
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import set_local_domain_sql_backend_override
from corehq.util.log import with_progress_bar

from ...casediff import (
    ProcessNotAllowed,
    global_diff_state,
    get_casediff_state_path,
    make_result_saver,
)
from ...couchsqlmigration import (
    CouchSqlDomainMigrator,
    get_main_forms_iteration_stop_date,
    setup_logging,
)
from ...parallel import Pool
from ...util import get_ids_from_string_or_file

log = logging.getLogger(__name__)

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
                Diff specific cases. The value of this option may be
                'pending' to clear out in-process diffs OR 'with-diffs'
                to re-diff cases that previously had diffs OR a
                space-delimited list of case ids OR a path to a file
                containing a case id on each line. The path must begin
                with / or ./
            ''')
        parser.add_argument('-x', '--stop',
            dest="stop", action='store_true', default=False,
            help='''
                Stop and drop into debugger on first diff. A
                non-parallel iteration algorithm is used when this
                option is set.
            ''')
        parser.add_argument('-b', '--batch-size',
            dest="batch_size", default=100, type=int,
            help='''Diff cases in batches of this size.''')

    def handle(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(f'It looks like {domain} has already been migrated.')

        for opt in ["no_input", "state_dir", "live", "cases", "stop", "batch_size"]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')

        assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        setup_logging(self.state_dir, "case_diff", options['debug'])
        migrator = get_migrator(domain, self.state_dir, self.live)
        msg = do_case_diffs(migrator, self.cases, self.stop, self.batch_size)
        if msg:
            sys.exit(msg)


def get_migrator(domain, state_dir, live):
    # Set backend for CouchSqlDomainMigrator._check_for_migration_restrictions
    set_local_domain_sql_backend_override(domain)
    return CouchSqlDomainMigrator(
        domain, state_dir, live_migrate=live, diff_process=None)


def do_case_diffs(migrator, cases, stop, batch_size):
    casediff = CaseDiffTool(migrator, cases, stop, batch_size)
    log.info("cutoff_date = %s", casediff.cutoff_date)
    with casediff.context() as add_cases:
        save_result = make_result_saver(casediff.statedb, add_cases)
        for data in casediff.iter_case_diff_results():
            save_result(data)
    if casediff.should_diff_pending():
        return PENDING_WARNING


class CaseDiffTool:

    def __init__(self, migrator, cases, stop, batch_size):
        self.migrator = migrator
        self.domain = migrator.domain
        self.statedb = migrator.statedb
        self.cases = cases
        self.stop = stop
        self.batch_size = batch_size
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
            with counter('diff_cases', 'CommCareCase.id') as add_cases:
                yield add_cases

    def iter_case_diff_results(self):
        if self.cases is None:
            return self.resumable_iter_diff_cases()
        if self.cases == "pending":
            return self.iter_diff_cases(self.get_pending_cases())
        if self.cases == "with-diffs":
            return self.iter_diff_cases_with_diffs()
        case_ids = get_ids_from_string_or_file(self.cases)
        return self.iter_diff_cases(case_ids, log_cases=True)

    def resumable_iter_diff_cases(self):
        def diff_batch(case_ids):
            case_ids = list(case_ids)
            statedb.add_cases_to_diff(case_ids)  # add pending cases
            return case_ids

        statedb = self.statedb
        case_ids = self.migrator._get_resumable_iterator(
            ['CommCareCase.id'],
            progress_name="Diff",
            offset_key='CommCareCase.id',
        )
        return self.iter_diff_cases(case_ids, diff_batch)

    def iter_diff_cases_with_diffs(self):
        count = self.statedb.count_case_ids_with_diffs()
        cases = self.statedb.iter_case_ids_with_diffs()
        cases = with_progress_bar(cases, count, prefix="Cases with diffs", oneline=False)
        return self.iter_diff_cases(cases)

    def iter_diff_cases(self, case_ids, batcher=None, log_cases=False):
        def list_or_stop(items):
            if self.is_stopped():
                raise StopIteration
            return list(items)

        batches = chunked(case_ids, self.batch_size, batcher or list_or_stop)
        if not self.stop:
            yield from self.pool.imap_unordered(load_and_diff_cases, batches)
            return
        stop = [1]
        with global_diff_state(*self.initargs), suppress(pdb.bdb.BdbQuit):
            for batch in batches:
                data = load_and_diff_cases(batch, log_cases=log_cases)
                yield data
                diffs = {case_id: diffs for x, case_id, diffs in data.diffs if diffs}
                if diffs:
                    log.info("found cases with diffs:\n%s", format_diffs(diffs))
                    if stop:
                        pdb.set_trace()

    def is_stopped(self):
        return self.migrator.stopper.clean_break

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
        return Pool(
            processes=os.cpu_count() * 2,
            initializer=init_worker,
            initargs=self.initargs,
            maxtasksperchild=100,
        )

    @property
    def initargs(self):
        return self.domain, self.statedb.get_no_action_case_forms(), self.cutoff_date


def load_and_diff_cases(case_ids, log_cases=False):
    from ...casediff import _diff_state, get_couch_cases, diff_cases
    should_diff = _diff_state.should_diff
    couch_cases = {c.case_id: c.to_json()
        for c in get_couch_cases(case_ids) if should_diff(c)}
    if log_cases:
        skipped = [id for id in case_ids if id not in couch_cases]
        if skipped:
            log.info("skipping cases modified since cutoff date: %s", skipped)
    return diff_cases(couch_cases, log_cases=log_cases)


def iter_sql_cases_with_sorted_transactions(domain):
    from corehq.form_processor.models import CommCareCaseSQL, CaseTransaction
    from corehq.sql_db.util import get_db_aliases_for_partitioned_query
    from ...rebuildcase import SortTransactionsRebuild

    sql = f"""
        SELECT cx.case_id
        FROM {CommCareCaseSQL._meta.db_table} cx
        INNER JOIN {CaseTransaction._meta.db_table} tx ON cx.case_id = tx.case_id
        WHERE cx.domain = %s AND tx.details LIKE %s
    """
    reason = f'%{SortTransactionsRebuild._REASON}%'
    for dbname in get_db_aliases_for_partitioned_query():
        with CommCareCaseSQL.get_cursor_for_partition_db(dbname) as cursor:
            cursor.execute(sql, [domain, reason])
            yield from iter(set(case_id for case_id, in cursor.fetchall()))


def format_diffs(diff_dict):
    lines = []
    for doc_id, diffs in sorted(diff_dict.items()):
        lines.append(doc_id)
        for diff in diffs:
            if len(repr(diff.old_value) + repr(diff.new_value)) > 60:
                lines.append(f"  {diff.diff_type} {list(diff.path)}")
                lines.append(f"    - {diff.old_value!r}")
                lines.append(f"    + {diff.new_value!r}")
            else:
                lines.append(
                    f"  {diff.diff_type} {list(diff.path)}"
                    f" {diff.old_value!r} -> {diff.new_value!r}"
                )
    return "\n".join(lines)


def init_worker(domain, *args):
    def on_break(signum, frame):
        nonlocal clean_break
        if clean_break:
            raise KeyboardInterrupt
        print("clean break... (Ctrl+C to abort)")
        clean_break = True

    clean_break = False
    signal.signal(signal.SIGINT, on_break)
    set_local_domain_sql_backend_override(domain)
    return global_diff_state(domain, *args)
