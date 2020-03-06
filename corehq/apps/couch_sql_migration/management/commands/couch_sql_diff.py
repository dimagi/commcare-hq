import csv
import json
import logging
import os
import sys
from itertools import groupby

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import retry_on_couch_error

from corehq.apps.domain.models import Domain
from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
)
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.log import with_progress_bar

from ...casediff import get_couch_cases
from ...casedifftool import do_case_diffs, format_diffs, get_migrator
from ...couchsqlmigration import setup_logging
from ...diff import filter_case_diffs, filter_form_diffs
from ...missingdocs import MissingIds
from ...rewind import IterationState
from ...statedb import Counts, StateDB, open_state_db

log = logging.getLogger(__name__)

CASES = "cases"
SHOW = "show"
FILTER = "filter"

PREPARE = "prepare"
DELETE = "delete"


class Command(BaseCommand):
    help = "Diff data in couch and SQL with parallel worker processes"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('action', choices=[CASES, SHOW, FILTER], help="""
            "cases": diff cases.
            "show": print diffs.
            "filter": filter diffs, removing ones that would normally be
            filtered out. This is useful when new diff ignore rules have
            been added that apply to existing diff records.
        """)
        parser.add_argument('--no-input', action='store_true', default=False)
        parser.add_argument('--debug', action='store_true', default=False)
        parser.add_argument('--state-dir', dest='state_path',
            default=os.environ.get("CCHQ_MIGRATION_STATE_DIR"),
            required="CCHQ_MIGRATION_STATE_DIR" not in os.environ,
            help="""
                Directory for couch2sql logs and migration state. This must not
                reside on an NFS volume for migration state consistency.
                Can be set in environment: CCHQ_MIGRATION_STATE_DIR
            """)
        parser.add_argument('--select',
            help='''
                Diff specific items. The value of this option may be
                'pending' to clear out in-process diffs OR 'with-diffs'
                to re-diff items that previously had diffs OR a
                space-delimited list of case ids OR a path to a file
                containing a case id on each line. The path must begin
                with / or ./

                With the "show" or "filter" actions, this option should
                be a doc type. All form and case doc types are
                supported.
            ''')
        parser.add_argument('--changes',
            dest="changes", action='store_true', default=False,
            help="Show changes instead of diffs. Only valid with 'show' action")
        parser.add_argument('--csv',
            dest="csv", action='store_true', default=False,
            help="Output diffs to stdout in CSV format.")
        parser.add_argument('-x', '--stop',
            dest="stop", action='store_true', default=False,
            help='''
                Stop and drop into debugger on first diff. A
                non-parallel iteration algorithm is used when this
                option is set. For "filter --dry-run" propmt to stop
                after each batch.
            ''')
        parser.add_argument('-b', '--batch-size',
            dest="batch_size", default=100, type=int,
            help='''Diff batch size.''')
        parser.add_argument('--reset', choices=[PREPARE, DELETE],
            help='''
                Reset state to start fresh. This is a two-phase
                operation: first run with --reset=prepare to save
                resumable iterator state into the statedb. Then run with
                --reset=delete to permanently delete diffs, changes, and
                progress information from the statedb.
            ''')
        parser.add_argument('-n', '--dry-run',
            dest="dry_run", action='store_true', default=False,
            help="show what would happen, but do not commit changes")

    def handle(self, domain, action, **options):
        if action == CASES and should_use_sql_backend(domain):
            raise CommandError(f'It looks like {domain} has already been migrated.')

        for opt in [
            "no_input",
            "debug",
            "state_path",
            "select",
            "stop",
            "changes",
            "csv",
            "batch_size",
            "reset",
            "dry_run",
        ]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')
        if self.changes and action != SHOW:
            raise CommandError(f'{action} --changes not allowed')
        if self.csv and action != SHOW:
            raise CommandError(f'{action} --csv not allowed')
        if self.dry_run and action != FILTER:
            raise CommandError(f'{action} --dry-run not allowed')

        if self.reset:
            if action != CASES:
                raise CommandError(f'{action} --reset not allowed')
            self.do_reset(action, domain)
            return

        if action not in [SHOW, FILTER]:
            assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        do_action = getattr(self, "do_" + action)
        msg = do_action(domain)
        if msg:
            sys.exit(msg)

    def do_cases(self, domain):
        """Diff cases"""
        setup_logging(self.state_path, "case_diff", self.debug)
        migrator = get_migrator(domain, self.state_path)
        return do_case_diffs(migrator, self.select, self.stop, self.batch_size)

    def do_show(self, domain):
        """Show diffs from state db"""
        statedb = self.open_state_db(domain)
        print(f"showing diffs from {statedb}", file=sys.stderr)
        if self.changes:
            items = statedb.iter_doc_changes(self.select)
        else:
            items = statedb.iter_doc_diffs(self.select)
        prompt = not self.csv
        if self.csv:
            items = self.with_progress(items, statedb)
            print(CSV_HEADERS, file=sys.stdout)
        try:
            for doc_diffs in chunked(items, self.batch_size, list):
                format_doc_diffs(doc_diffs, self.csv, self.changes, sys.stdout)
                if len(doc_diffs) < self.batch_size:
                    continue
                if prompt and not confirm("show more?"):
                    break
        except (KeyboardInterrupt, BrokenPipeError):
            pass

    def do_filter(self, domain):
        def update_doc_diffs(doc_diffs):
            ids = [d[1] for d in doc_diffs]
            sql_docs = get_sql_docs(ids)
            couch_docs = get_couch_docs(ids)
            new_diffs = []
            for kind, doc_id, diffs in doc_diffs:
                couch_json = get_json(kind, doc_id, couch_docs)
                sql_json = get_json(kind, doc_id, sql_docs)
                json_diffs = [json_diff(d) for d in diffs]
                new_diffs = filter_diffs(couch_json, sql_json, json_diffs)
                if self.dry_run:
                    print(f"{kind} {doc_id}: {len(diffs)} -> {len(new_diffs)} diffs")
                else:
                    statedb.add_diffs(kind, doc_id, new_diffs)

        def get_json(kind, doc_id, docs):
            doc = docs.get(doc_id)
            return doc.to_json() if doc is not None else {"doc_type": kind}

        def json_diff(diff):
            jd = diff.json_diff
            return jd._replace(path=tuple(jd.path))

        statedb = self.open_state_db(domain, readonly=self.dry_run)
        if self.changes:
            raise NotImplementedError("filter --changes")
        if self.select in MissingIds.form_types:
            def get_sql_docs(ids):
                return {f.form_id: f for f in FormAccessorSQL.get_forms(ids)}

            def get_couch_docs(ids):
                return {f.form_id: f for f in get_couch_forms(ids)}

            filter_diffs = filter_form_diffs
        elif self.select in MissingIds.case_types:
            def get_sql_docs(ids):
                return {c.case_id: c for c in CaseAccessorSQL.get_cases(ids)}

            def get_couch_docs(ids):
                return {c.case_id: c for c in get_couch_cases(ids)}

            filter_diffs = filter_case_diffs
        else:
            raise NotImplementedError(f"--select={self.select}")
        prompt = self.dry_run and self.stop
        doc_diffs = statedb.iter_doc_diffs(self.select)
        doc_diffs = self.with_progress(doc_diffs, statedb)
        for batch in chunked(doc_diffs, self.batch_size, list):
            update_doc_diffs(batch)
            if prompt and not confirm("show more?"):
                break

    def with_progress(self, doc_diffs, statedb):
        counts = statedb.get_doc_counts()
        if self.select:
            count = counts.get(self.select, Counts())
            count = count.changes if self.changes else count.diffs
        else:
            count = sum(c.changes if self.changes else c.diffs
                        for c in counts.values())
        return with_progress_bar(
            doc_diffs, count, "Docs", oneline=False, stream=sys.stderr)

    def do_reset(self, action, domain):
        itr_doc_type = {"cases": "CommCareCase.id"}[action]
        db = self.open_state_db(domain, readonly=False)
        itr_state = IterationState(db, domain, itr_doc_type)
        if self.reset == PREPARE:
            self.prepare_reset(action, db, itr_state)
        else:
            assert self.reset == DELETE, self.reset
            self.reset_statedb(action, db, itr_state)

    def open_state_db(self, domain, *, readonly=True):
        state_path = os.path.expanduser(self.state_path)
        if os.path.isdir(state_path):
            return open_state_db(domain, state_path, readonly=readonly)
        if os.path.isfile(state_path):
            return StateDB.open(domain, state_path, readonly=readonly)
        sys.exit(f"file or directory not found:\n{state_path}")

    def prepare_reset(self, action, db, itr_state):
        self.setup_reset_logging()
        log.info(f"Saving {action} resumable iterator state in {db}")
        value = itr_state.value
        if itr_state.backup_resume_state(value):
            log.info(
                f"Backup {db.db_filepath} in a safe place.\n\n"
                f"Then run `{action} --reset=delete` to permanently delete "
                f"existing diffs, changes, and progress information from "
                f"{db.db_filepath}"
            )

    def reset_statedb(self, action, db, itr_state):
        print(
            f"This will permanently delete existing diffs, changes, and "
            f"progress information for {action} from {db.db_filepath}.\n"
            f"\n"
            f"You should have already run `{action} --reset=prepare` and "
            f"made a backup prior to performing this step. Go back and do "
            f"that now if necessary."
        )
        ok = input("Enter 'ok' to delete: ").lower()
        if ok != "ok":
            return sys.exit("aborting...")
        self.setup_reset_logging()
        log.info(f"deleting {action} iteration state from {db}")
        self.delete_resumable_iteration_state(itr_state)
        self.reset_doc_count(db, itr_state.doc_type)
        self.reset_diff_data(db, action)
        log.info("vacuum state db")
        db.vacuum()
        log.info("done")

    def setup_reset_logging(self):
        path = self.state_path
        log_dir = os.path.dirname(path) if os.path.isfile(path) else path
        setup_logging(log_dir, "couch_sql_diff", self.debug)

    def delete_resumable_iteration_state(self, itr_state):
        pretty_value = json.dumps(itr_state.value, indent=2)
        log.info("deleting iteration state from Couch: %s", pretty_value)
        itr_state.drop_from_couch()

    def reset_doc_count(self, db, itr_doc_type):
        counts = db.get("doc_counts")
        if itr_doc_type not in counts:
            log.warning(f"unexpected: {itr_doc_type} not in {counts}")
        else:
            log.info(f"doc_counts['{itr_doc_type}'] == {counts[itr_doc_type]}")
            counts[itr_doc_type] = 0
            db.set("doc_counts", counts)

    def reset_diff_data(self, db, action):
        from ...statedb import (
            CaseToDiff,
            DiffedCase,
            DocChanges,
            DocCount,
            DocDiffs,
            MissingDoc,
        )

        def delete(model, kind):
            log.info(f"DELETE FROM {model.__tablename__} WHERE kind = '{kind}'")
            (
                session.query(model)
                .filter(model.kind == kind)
                .delete(synchronize_session=False)
            )

        def delete_all(model):
            log.info(f"DELETE FROM {model.__tablename__}")
            session.query(model).delete(synchronize_session=False)

        assert action == "cases", action
        with db.session() as session:
            delete(DocCount, "CommCareCase")
            delete(DocDiffs, "CommCareCase")
            delete(DocChanges, "CommCareCase")
            delete(MissingDoc, "CommCareCase")
            delete(MissingDoc, "CommCareCase-Deleted")
            delete(MissingDoc, "CommCareCase-couch")
            delete_all(CaseToDiff)
            delete_all(DiffedCase)


def format_doc_diffs(doc_diffs, csv, changes, stream):
    json_diffs = iter_json_diffs(doc_diffs)
    if csv:
        related = dict(iter_related(doc_diffs))
        csv_diffs(json_diffs, related, changes, stream)
    else:
        print(format_diffs(json_diffs, changes), file=stream)


CASE = "CommCareCase"
STOCK = "stock state"
CSV_HEADERS = ",".join([
    "doc_type",
    "doc_id",
    "user_id",
    "server_date",
    "diff_type",
    "path",
    "old_value",
    "new_value",
    # "reason" is added to rows for --changes, but not here
])


def csv_diffs(json_diffs, related, changes, stream):
    rows = []
    for kind, doc_id, diffs in json_diffs:
        user_id, server_date = related[kind].get(doc_id, ("", ""))
        for diff in sorted(diffs, key=lambda d: (d.diff_type, d.path)):
            row = [
                kind,
                doc_id,
                user_id,
                server_date,
                diff.diff_type,
                "/".join(diff.path),
                diff.old_value,
                diff.new_value,
            ]
            if changes:
                row.append(diff.reason)
            rows.append(row)
    writer = csv.writer(stream)
    writer.writerows(rows)


def iter_json_diffs(doc_diffs):
    def iter_stock_diffs(stock_diffs):
        def key(diff):
            return (diff.kind, diff.doc_id)
        for (kind, doc_id), diffs in groupby(sorted(stock_diffs, key=key), key=key):
            yield kind, doc_id, [d.json_diff for d in diffs]

    for kind, doc_id, diffs in doc_diffs:
        assert kind != STOCK
        dxx = [d.json_diff for d in diffs if d.kind != STOCK]
        yield kind, doc_id, dxx
        stock_diffs = [d for d in diffs if d.kind == STOCK]
        if stock_diffs:
            yield from iter_stock_diffs(stock_diffs)


def iter_related(doc_diffs):
    """Get user_id and server_date for each item in doc_diffs

    :yields: `kind, {doc_id: (user_id, server_date), ...}`
    """
    def key(item):
        return item[1][0].kind

    def get_related(kind, doc_ids):
        if kind.startswith(CASE):
            return get_case_related(doc_ids)
        assert kind != STOCK
        return get_form_related(doc_ids)

    stock_related = {}
    for kind, group in groupby(sorted(doc_diffs), key=lambda x: x[0]):
        group = list(group)
        doc_ids = [doc_id for x, doc_id, x in group]
        related = get_related(kind, doc_ids)
        assert len(related) == len(doc_ids), (kind, set(doc_ids) - set(related))
        if kind == CASE:
            for k, doc_id, diffs in group:
                for diff in diffs:
                    if diff.kind == STOCK:
                        stock_related[diff.doc_id] = related[doc_id]
        yield kind, related
    yield STOCK, stock_related


def get_case_related(case_ids):
    def server_date(case):
        return max(a.server_date for a in case.actions if a.server_date)
    return {
        case.case_id: (case.user_id, server_date(case))
        for case in get_couch_cases(case_ids)
    }


def get_form_related(form_ids):
    return {
        form.form_id: (form.user_id, form.received_on)
        for form in get_couch_forms(form_ids)
    }


@retry_on_couch_error
def get_couch_forms(form_ids):
    return FormAccessorCouch.get_forms(form_ids)


def confirm(msg):
    return input(msg + " (Y/n) ").lower().strip() in ['', 'y', 'yes']
