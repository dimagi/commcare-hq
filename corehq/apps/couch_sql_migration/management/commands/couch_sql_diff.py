import json
import logging
import os
import sys
from itertools import groupby

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dimagi.utils.chunked import chunked

from corehq.apps.domain.models import Domain
from corehq.form_processor.utils import should_use_sql_backend

from ...casedifftool import do_case_diffs, format_diffs, get_migrator
from ...couchsqlmigration import setup_logging
from ...rewind import IterationState
from ...statedb import StateDB, open_state_db

log = logging.getLogger(__name__)

CASES = "cases"
SHOW = "show"

PREPARE = "prepare"
DELETE = "delete"


class Command(BaseCommand):
    help = "Diff data in couch and SQL with parallel worker processes"

    def add_arguments(self, parser):
        parser.add_argument('action', choices=[CASES, SHOW])
        parser.add_argument('domain')
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

                With the "show" action, this option should be a doc type.
            ''')
        parser.add_argument('--changes',
            dest="changes", action='store_true', default=False,
            help="Show changes instead of diffs. Only valid with 'show' action")
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
        parser.add_argument('--reset', choices=[PREPARE, DELETE],
            help='''
                Reset state to start fresh. This is a two-phase
                operation: first run with --reset=prepare to save
                resumable iterator state into the statedb. Then run with
                --reset=delete to permanently delete diffs, changes, and
                progress information from the statedb.
            ''')

    def handle(self, action, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(f'It looks like {domain} has already been migrated.')

        for opt in [
            "no_input",
            "debug",
            "state_path",
            "live",
            "cases",
            "stop",
            "changes",
            "batch_size",
            "reset",
        ]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')
        if self.changes and action != SHOW:
            raise CommandError('--changes only allowed with "show" action')

        if self.reset:
            if action == SHOW:
                raise CommandError(f'invalid action for --reset: {action}')
            self.do_reset(action, domain)
            return

        if action != SHOW:
            assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        do_action = getattr(self, "do_" + action)
        msg = do_action(domain)
        if msg:
            sys.exit(msg)

    def do_cases(self, domain):
        """Diff cases"""
        setup_logging(self.state_path, "case_diff", self.debug)
        migrator = get_migrator(domain, self.state_path, self.live)
        return do_case_diffs(migrator, self.cases, self.stop, self.batch_size)

    def do_show(self, domain):
        """Show diffs from state db"""
        def iter_json_diffs(doc_diffs):
            for doc_id, diffs in doc_diffs:
                yield doc_id, [d.json_diff for d in diffs if d.kind != "stock state"]
                stock_diffs = [d for d in diffs if d.kind == "stock state"]
                if stock_diffs:
                    yield from iter_stock_diffs(stock_diffs)

        def iter_stock_diffs(diffs):
            def key(diff):
                return diff.doc_id
            for doc_id, diffs in groupby(sorted(diffs, key=key), key=key):
                yield doc_id, [d.json_diff for d in diffs]

        statedb = self.open_state_db(domain)
        print(f"showing diffs from {statedb}")
        if self.changes:
            items = statedb.iter_doc_changes(self.cases)
        else:
            items = statedb.iter_doc_diffs(self.cases)
        json_diffs = iter_json_diffs(items)
        for chunk in chunked(json_diffs, self.batch_size, list):
            print(format_diffs(dict(chunk)))
            if not confirm("show more?"):
                break

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
            delete(MissingDoc, "CommCareCase-couch")
            delete_all(CaseToDiff)
            delete_all(DiffedCase)


def confirm(msg):
    return input(msg + " (Y/n) ").lower().strip() in ['', 'y', 'yes']
