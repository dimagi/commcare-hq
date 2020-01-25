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
from ...statedb import StateDB, open_state_db

CASES = "cases"
SHOW = "show"


class Command(BaseCommand):
    help = "Diff data in couch and SQL with parallel worker processes"

    def add_arguments(self, parser):
        parser.add_argument('action', choices=[CASES, SHOW])
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

                With the "show" action, this option should be a doc type.
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

    def handle(self, action, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(f'It looks like {domain} has already been migrated.')

        for opt in [
            "no_input",
            "debug",
            "state_dir",
            "live",
            "cases",
            "stop",
            "batch_size",
        ]:
            setattr(self, opt, options[opt])

        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('--no-input only allowed for unit testing')

        if action != "show":
            assert Domain.get_by_name(domain), f'Unknown domain "{domain}"'
        do_action = getattr(self, "do_" + action)
        msg = do_action(domain)
        if msg:
            sys.exit(msg)

    def do_cases(self, domain):
        """Diff cases"""
        setup_logging(self.state_dir, "case_diff", self.debug)
        migrator = get_migrator(domain, self.state_dir, self.live)
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

        if os.path.isdir(self.state_dir):
            statedb = open_state_db(domain, self.state_dir)
        elif os.path.isfile(self.state_dir):
            statedb = StateDB.open(domain, self.state_dir, readonly=True)
        else:
            sys.exit(f"file or directory not found:\n{self.state_dir}")
        print(f"showing diffs from {statedb}")
        json_diffs = iter_json_diffs(statedb.iter_doc_diffs(self.cases))
        for chunk in chunked(json_diffs, self.batch_size, list):
            print(format_diffs(dict(chunk)))
            if not confirm("show more?"):
                break


def confirm(msg):
    return input(msg + " (Y/n) ").lower().strip() in ['', 'y', 'yes']
