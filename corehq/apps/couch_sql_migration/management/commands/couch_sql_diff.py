import logging
import os
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
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    LedgerAccessorSQL,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import set_local_domain_sql_backend_override

from ...casediff import filter_missing_cases
from ...couchsqlmigration import (
    CouchSqlDomainMigrator,
    get_main_forms_iteration_stop_date,
    setup_logging,
)
from ...diff import filter_case_diffs, filter_ledger_diffs
from ...parallel import Pool

log = logging.getLogger(__name__)

DIFF_BATCH_SIZE = 100


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

    def handle(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError('It looks like {} has already been migrated.'.format(domain))

        for opt in ["no_input", "state_dir", "live"]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')

        assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        setup_logging(self.state_dir, "case_diff", options['debug'])
        migrator = get_migrator(domain, self.state_dir, self.live)
        msg = do_case_diffs(migrator)
        if msg:
            sys.exit(msg)


def get_migrator(domain, state_dir, live):
    # Set backend for CouchSqlDomainMigrator._check_for_migration_restrictions
    set_local_domain_sql_backend_override(domain)
    return CouchSqlDomainMigrator(
        domain, state_dir, live_migrate=live, diff_process=None)


def do_case_diffs(migrator):
    def save_result(data):
        log.debug(data)
        add_cases(len(data.doc_ids))
        statedb.add_diffed_cases(data.doc_ids)
        for doc_type, doc_id, diffs in data.diffs:
            statedb.add_diffs(doc_type, doc_id, diffs)
        for doc_type, doc_ids in data.missing_docs:
            statedb.add_missing_docs(doc_type, doc_ids)

    casediff = CaseDiffTool(migrator)
    statedb = casediff.statedb
    with casediff.context() as add_cases:
        for data in casediff.iter_case_diff_results():
            save_result(data)


class CaseDiffTool:

    def __init__(self, migrator):
        self.migrator = migrator
        self.domain = migrator.domain
        self.statedb = migrator.statedb
        if migrator.live_migrate:
            assert not hasattr(migrator.stopper, "stop_date")  # TODO use if set
            cutoff_date = get_main_forms_iteration_stop_date(
                self.domain, self.statedb.unique_id)
            migrator.stopper.stop_date = cutoff_date
        else:
            cutoff_date = None
        self.cutoff_date = cutoff_date

    @contextmanager
    def context(self):
        with self.migrator.counter as counter, self.migrator.stopper:
            with counter('diff_cases', 'CommCareCase') as add_cases:
                yield add_cases

    def iter_case_diff_results(self):
        batches = chunked(self.iter_case_ids(), DIFF_BATCH_SIZE, list)
        pool = Pool(initializer=init_worker, initargs=self.initargs, maxtasksperchild=100)
        yield from pool.imap_unordered(diff_cases, batches)

    def is_stopped(self):
        return self.migrator.stopper.clean_break

    def iter_case_ids(self):
        return self.migrator._get_resumable_iterator(
            ['CommCareCase.id'],
            progress_name="Diff",
            offset_key='CommCareCase.id',
        )

    @property
    def initargs(self):
        return self.statedb.get_no_action_case_forms(), self.cutoff_date


def diff_cases(case_ids):
    couch_cases = {c.case_id: c.to_json()
        for c in CaseAccessorCouch.get_cases(case_ids) if _state.should_diff(c)}
    case_ids = list(couch_cases)
    data = DiffData(case_ids)
    sql_case_ids = set()
    for sql_case in CaseAccessorSQL.get_cases(case_ids):
        case_id = sql_case.case_id
        sql_case_ids.add(case_id)
        couch_case = couch_cases[case_id]
        diffs = diff_case(sql_case, couch_case)
        data.diffs.append((couch_case['doc_type'], case_id, diffs))

    data.diffs.extend(iter_ledger_diffs(case_ids))
    add_missing_docs(data, couch_cases, sql_case_ids)
    return data


def diff_case(sql_case, couch_case):
    sql_case_json = sql_case.to_json()
    diffs = json_diff(couch_case, sql_case_json, track_list_indices=False)
    return filter_case_diffs(couch_case, sql_case_json, diffs, _state)


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
        missing_cases = [couch_cases[x] for x in only_in_couch]
        log.debug("Found %s missing SQL cases", len(missing_cases))
        for doc_type, doc_ids in filter_missing_cases(missing_cases):
            data.missing_docs.append((doc_type, doc_ids))


def init_worker(*args):
    global _state
    _state = WorkerState(*args)


@attr.s
class DiffData:
    doc_ids = attr.ib()
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
