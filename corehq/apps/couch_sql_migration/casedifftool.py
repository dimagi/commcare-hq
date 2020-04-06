import logging
import os
import pdb
import signal
from contextlib import contextmanager, suppress

from django.db import close_old_connections
from django.db.utils import DatabaseError, InterfaceError

from dimagi.utils.chunked import chunked
from dimagi.utils.retry import retry_on

from corehq.form_processor.utils.general import set_local_domain_sql_backend_override
from corehq.util.log import with_progress_bar

from .casediff import (
    add_cases_missing_from_couch,
    diff_cases,
    get_couch_cases,
    global_diff_state,
    make_result_saver,
    should_diff,
)
from .casediffqueue import ProcessNotAllowed, get_casediff_state_path
from .couchsqlmigration import (
    CouchSqlDomainMigrator,
    get_main_forms_iteration_stop_date,
)
from .parallel import Pool
from .progress import MigrationStatus, get_couch_sql_migration_status
from .util import get_ids_from_string_or_file

log = logging.getLogger(__name__)

PENDING_WARNING = "Diffs pending. Run again with --cases=pending"


def get_migrator(domain, state_dir):
    # Set backend for CouchSqlDomainMigrator._check_for_migration_restrictions
    status = get_couch_sql_migration_status(domain)
    live_migrate = status == MigrationStatus.DRY_RUN
    set_local_domain_sql_backend_override(domain)
    return CouchSqlDomainMigrator(
        domain, state_dir, live_migrate=live_migrate, case_diff="none")


def do_case_diffs(migrator, cases, stop, batch_size):
    """Diff cases and save the results

    :param migrator: CouchSqlDomainMigrator instance. See also `get_migrator`.
    :param cases: string specifying a subset of cases to be diffed. All
    cases will be diffed if `None`. Accepted values:

        - 'pending': clear out in-process diffs
        - 'with-diffs': re-diff cases that previously had diffs
        - a space-delimited list of case ids
        - a path to a file containing a case id on each line. The path must
          begin with / or ./

    :param stop: Boolean. If false perform diffs in parallel processes.
    If true perform diffs in the main process and drop into a pdb
    session when the first batch of cases with diffs is encountered.
    """
    casediff = CaseDiffTool(migrator, stop, batch_size)
    with migrator.counter, migrator.stopper:
        casediff.diff_cases(cases)
    if cases is None and casediff.should_diff_pending():
        return PENDING_WARNING


class CaseDiffTool:
    """A multi-process case diff tool

    This tool performs case diffs but does not save the results.
    See also `do_case_diffs`.
    """

    def __init__(self, migrator, stop=False, batch_size=100):
        self.migrator = migrator
        self.domain = migrator.domain
        self.statedb = migrator.statedb
        self.stop = stop
        self.batch_size = batch_size
        if not migrator.live_migrate:
            cutoff_date = None
        elif hasattr(migrator.stopper, "stop_date"):
            cutoff_date = migrator.stopper.stop_date
        else:
            cutoff_date = get_main_forms_iteration_stop_date(self.statedb)
            migrator.stopper.stop_date = cutoff_date
        self.cutoff_date = cutoff_date
        self.lock_out_casediff_process()

    def lock_out_casediff_process(self):
        if not self.statedb.get(ProcessNotAllowed.__name__):
            state_path = get_casediff_state_path(self.statedb.db_filepath)
            if os.path.exists(state_path):
                self.statedb.clone_casediff_data_from(state_path)
            self.statedb.set(ProcessNotAllowed.__name__, True)

    def diff_cases(self, cases=None):
        log.info("case diff cutoff date = %s", self.cutoff_date)
        with self.migrator.counter('diff_cases', 'CommCareCase.id') as add_cases:
            save_result = make_result_saver(self.statedb, add_cases)
            for data in self.iter_case_diff_results(cases):
                save_result(data)

    def iter_case_diff_results(self, cases):
        if cases is None:
            return self.resumable_iter_diff_cases()
        if cases == "pending":
            return self.iter_diff_cases(self.get_pending_cases())
        if cases == "with-diffs":
            return self.iter_diff_cases_with_diffs()
        case_ids = get_ids_from_string_or_file(cases)
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
                diffs = [(kind, case_id, diffs) for kind, case_id, diffs in data.diffs if diffs]
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

    should_diff_pending = get_pending_cases

    @property
    def pool(self):
        return Pool(
            processes=os.cpu_count() * 2,
            initializer=init_worker,
            initargs=self.initargs,
        )

    @property
    def initargs(self):
        return self.domain, self.statedb.get_no_action_case_forms(), self.cutoff_date


def load_and_diff_cases(case_ids, log_cases=False):
    couch_cases = get_couch_cases(case_ids)
    cases_to_diff = {c.case_id: c.to_json() for c in couch_cases if should_diff(c)}
    if log_cases:
        skipped = {c.case_id for c in couch_cases} - cases_to_diff.keys()
        if skipped:
            log.info("skipping cases modified since cutoff date: %s", skipped)
    data = diff_cases_with_retry(cases_to_diff, log_cases=log_cases)
    if len(set(case_ids)) > len(couch_cases):
        missing_ids = set(case_ids) - {c.case_id for c in couch_cases}
        add_cases_missing_from_couch(data, missing_ids)
    return data


def _close_connections(err):
    """Close old connections, then return true to retry"""
    log.warning("retry diff cases on %s: %s", type(err).__name__, err)
    close_old_connections()
    return True


@retry_on(DatabaseError, InterfaceError, should_retry=_close_connections)
def diff_cases_with_retry(*args, **kw):
    return diff_cases(*args, **kw)


def iter_sql_cases_with_sorted_transactions(domain):
    from corehq.form_processor.models import CommCareCaseSQL, CaseTransaction
    from corehq.sql_db.util import get_db_aliases_for_partitioned_query
    from .rebuildcase import SortTransactionsRebuild

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


def format_diffs(json_diffs, changes=False):
    lines = []
    for kind, doc_id, diffs in sorted(json_diffs, key=lambda x: x[1]):
        lines.append(f"{kind} {doc_id} {diffs[0].reason if changes else ''}")
        for diff in sorted(diffs, key=lambda d: (d.diff_type, d.path)):
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
    reset_django_db_connections()
    reset_couchdb_connections()
    reset_blobdb_connections()
    reset_redis_connections()
    signal.signal(signal.SIGINT, on_break)
    set_local_domain_sql_backend_override(domain)
    return global_diff_state(domain, *args)


def reset_django_db_connections():
    # cannot use db.connections.close_all() because that results in
    # InterfaceError: connection already closed
    # see also https://github.com/psycopg/psycopg2/blob/master/psycopg/connection_type.c
    #   /* close the connection only if this is the same process it was created
    #    * into, otherwise using multiprocessing we may close the connection
    #    * belonging to another process. */
    from django import db
    for alias in db.connections:
        try:
            del db.connections[alias]
        except AttributeError:
            pass


def reset_couchdb_connections():
    from couchdbkit.ext.django.loading import CouchdbkitHandler
    dbs = CouchdbkitHandler.__shared_state__["_databases"]
    for db in dbs.values():
        server = db[0] if isinstance(db, tuple) else db.server
        with safe_socket_close():
            server.cloudant_client.r_session.close()


def reset_blobdb_connections():
    from corehq.blobs import _db, get_blob_db
    if _db:
        assert len(_db) == 1, _db
        old_blob_db = get_blob_db()
        _db.pop()
        assert get_blob_db() is not old_blob_db


def reset_redis_connections():
    from django_redis.pool import ConnectionFactory
    for pool in ConnectionFactory._pools.values():
        pool.reset()


@contextmanager
def safe_socket_close():
    from functools import partial
    from gevent._socket3 import socket

    def safe_cancel_wait(hub_cancel_wait, *args):
        try:
            hub_cancel_wait(*args)
        except ValueError as err:
            if str(err) != "operation on destroyed loop":
                raise

    def drop_events(self):
        self.hub.cancel_wait = partial(safe_cancel_wait, self.hub.cancel_wait)
        try:
            return _drop_events(self)
        finally:
            del self.hub.cancel_wait
            assert self.hub.cancel_wait, "unexpected method removal"

    _drop_events = socket._drop_events
    socket._drop_events = drop_events
    try:
        yield
    finally:
        socket._drop_events = _drop_events
